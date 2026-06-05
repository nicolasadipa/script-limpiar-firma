"""
processor.py — Pipeline completo de limpieza y extracción de firmas manuscritas.

Pipeline probado y estable que funciona bien con CamScanner y escaneos:

El pipeline sigue estas etapas en orden:
  1. Remover footer de escáner (CamScanner, etc.)
  2. Corrección de iluminación (CLAHE en LAB)
  3. Conversión a escala de grises
  4. Eliminación de ruido (NLM denoising)
  5. Umbralización adaptativa (binarización)
  6. Limpieza morfológica (apertura)
  7. Eliminación de componentes pequeños (artefactos)
  8. Detección del área de la firma por contornos
  9. Recorte al bounding-box + padding
 10. Generación de máscara suave (anti-aliasing en bordes)
 11. Colorización a negro puro (#000000)
 12. Exportación a PNG con canal alfa (transparencia real)
 13. Escalado al tamaño de salida configurado
 14. Aumento de nitidez final (unsharp mask)
"""

from __future__ import annotations

import os
import cv2
import numpy as np

import config
from logger import setup_logger

logger = setup_logger()


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def _flatten_to_bgr(img: np.ndarray) -> np.ndarray:
    """
    Normaliza cualquier imagen leída a BGR de 3 canales, componiendo sobre
    fondo BLANCO si trae canal alfa.

    Antes el loader usaba cv2.IMREAD_COLOR, que descarta el alfa y aplana el
    fondo transparente sobre NEGRO. Para una firma exportada como PNG con
    transparencia (fondo transparente, trazos opacos) eso invertía por completo
    el mapa de tinta: el canal R quedaba bajo en toda la imagen y la
    binarización detectaba ~98% de la imagen como "tinta" → salida inservible.

    Componer sobre blanco preserva el color real del trazo (negro o azul) y
    deja el fondo claro, que es justo lo que el resto del pipeline espera.
    """
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    if img.shape[2] == 4:
        bgr   = img[:, :, :3].astype(np.float32)
        alpha = img[:, :, 3:4].astype(np.float32) / 255.0
        white = np.full_like(bgr, 255.0)
        comp  = bgr * alpha + white * (1.0 - alpha)
        transparent_pct = 100.0 * np.count_nonzero(img[:, :, 3] < 10) / img[:, :, 3].size
        logger.debug(
            f"Canal alfa detectado: compuesto sobre blanco "
            f"({transparent_pct:.1f}% del área era transparente)"
        )
        return comp.astype(np.uint8)

    return img


def _normalize_resolution(bgr: np.ndarray) -> np.ndarray:
    """
    Lleva el lado largo de la imagen a WORK_LONG_SIDE_PX cuando es más chica,
    para que el grosor de trazo caiga en el rango para el que está calibrado el
    resto del pipeline. Solo escala HACIA ARRIBA (interpolación cúbica): las
    imágenes grandes se devuelven sin tocar, así no se altera el caso que hoy
    ya funciona.
    """
    H, W      = bgr.shape[:2]
    long_side = max(H, W)
    target    = config.WORK_LONG_SIDE_PX

    if long_side >= target:
        return bgr

    scale = target / long_side
    new_W = int(round(W * scale))
    new_H = int(round(H * scale))
    logger.debug(
        f"Normalización de resolución: {W}x{H} → {new_W}x{new_H} (x{scale:.2f})"
    )
    return cv2.resize(bgr, (new_W, new_H), interpolation=cv2.INTER_CUBIC)


def _remove_scanner_footer(bgr: np.ndarray) -> np.ndarray:
    """
    Detecta y elimina el footer de escáner (CamScanner y similares) buscando
    una línea horizontal divisoria en el último 15% de la imagen.

    A diferencia de cortar siempre N píxeles fijos, esto:
      - No corta nada si la firma NO viene de un escáner con footer.
      - Si hay footer, lo corta justo en la línea divisoria (no encima de
        la firma ni dejando logo abajo).
    """
    H, W = bgr.shape[:2]

    if H < 300:
        return bgr

    search_start = int(H * 0.85)
    search_zone  = bgr[search_start:, :]
    gray_zone    = cv2.cvtColor(search_zone, cv2.COLOR_BGR2GRAY)

    # Detectar bordes horizontales fuertes en la zona inferior
    edges = cv2.Canny(gray_zone, 50, 150)
    horizontal_strength = np.sum(edges, axis=1)  # suma por fila

    # Una "línea divisoria" cubre >60% del ancho como borde fuerte
    line_threshold = W * 255 * 0.60
    candidate_rows = np.where(horizontal_strength > line_threshold)[0]

    if candidate_rows.size > 0:
        cutoff_y = search_start + int(candidate_rows[0])
        logger.debug(f"Footer detectado en y={cutoff_y} (H original={H})")
        return bgr[:cutoff_y, :]

    logger.debug("Sin footer de escáner detectado, no se recorta")
    return bgr


def _correct_illumination(bgr: np.ndarray) -> np.ndarray:
    """
    Iguala la iluminación usando CLAHE sobre el canal L del espacio LAB.
    Compensa sombras de escaneos y fotografías con iluminación lateral.
    """
    lab  = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(
        clipLimit=config.CLAHE_CLIP_LIMIT,
        tileGridSize=config.CLAHE_TILE_GRID,
    )
    l_eq = clahe.apply(l)

    lab_eq = cv2.merge([l_eq, a, b])
    return cv2.cvtColor(lab_eq, cv2.COLOR_LAB2BGR)


def _extract_ink_channel(bgr_corrected: np.ndarray, ink_color: str) -> np.ndarray:
    """
    Extrae el canal con MEJOR CONTRASTE según el color de tinta.

    AZUL: Usa saturación en HSV (azul puro = S alta, ruido = S baja)
    NEGRA: Usa canal R invertido (tinta negra = R bajo, fondo = R alto)

    Resultado: "Mapa de tinta" donde firma resalta más que en escala de grises.
    """
    if ink_color == "blue":
        # Para tinta azul: extraer saturación HSV
        hsv = cv2.cvtColor(bgr_corrected, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)

        # Azul puro tiene S alta, ruido tiene S baja
        # Invertir para que tinta = blanco (255)
        tinta_map = s

        logger.debug("Canal extraído para AZUL: Saturación (HSV)")

    else:  # black
        # Para tinta negra: extraer canal R invertido
        b, g, r = cv2.split(bgr_corrected)

        # Tinta negra tiene R bajo (0-50)
        # Fondo grisáceo tiene R alto (150-255)
        # Invertir: R bajo → 255 (blanco/tinta), R alto → 0 (negro/fondo)
        tinta_map = 255 - r

        logger.debug("Canal extraído para NEGRA: Inverso de R (BGR)")

    return tinta_map


def _denoise_tinta_map(tinta_map: np.ndarray) -> np.ndarray:
    """
    Denoising NLM sobre el mapa de tinta óptimo.

    El mapa de tinta ya tiene mejor contraste que escala de grises,
    así que el denoising es más efectivo.
    """
    return cv2.fastNlMeansDenoising(
        tinta_map,
        h=config.DENOISE_H,
        templateWindowSize=config.DENOISE_TEMPLATE_WS,
        searchWindowSize=config.DENOISE_SEARCH_WS,
    )


def _detect_ink_color(bgr_corrected: np.ndarray) -> str:
    """
    Detecta automáticamente si la firma es de tinta AZUL o NEGRA.

    Analiza los píxeles oscuros (gray < DARK_PIXEL_MAX_GRAY) y mide qué
    fracción de ellos cae en el rango azul de HSV. Si supera BLUE_INK_RATIO
    es tinta azul, si no, negra.

    Returns: "blue" o "black"
    """
    hsv  = cv2.cvtColor(bgr_corrected, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(bgr_corrected, cv2.COLOR_BGR2GRAY)
    h, s, _ = cv2.split(hsv)

    mask_dark = gray < config.DARK_PIXEL_MAX_GRAY
    mask_blue_ink = (
        (h >= config.BLUE_INK_HUE_MIN)
        & (h <= config.BLUE_INK_HUE_MAX)
        & (s >  config.BLUE_INK_MIN_SAT)
        & mask_dark
    )

    dark_count = int(np.sum(mask_dark))
    blue_count = int(np.sum(mask_blue_ink))
    blue_ratio = (blue_count / dark_count) if dark_count > 0 else 0.0

    ink_color = "blue" if blue_ratio > config.BLUE_INK_RATIO else "black"
    logger.info(
        f"Tinta detectada: {ink_color.upper()} "
        f"(azul_ratio={blue_ratio:.1%}, oscuros={dark_count})"
    )
    return ink_color


# Funciones de binarización antiguas removidas - ahora usamos mapa de tinta optimizado




def _binarize(tinta_map: np.ndarray, ink_color: str) -> np.ndarray:
    """
    Binariza el mapa de tinta. Resultado: firma=blanco(255), fondo=negro(0).

    En el mapa de tinta la firma ya tiene valores altos (saturación HSV para
    azul, canal R invertido para negra) y el fondo tiene valores bajos. Esa
    distribución bimodal limpia se separa muy bien con Otsu. Bajamos el corte
    de Otsu por THRESH_C para recuperar trazos finos sin tomar ruido de fondo.
    """
    otsu_thresh, _ = cv2.threshold(
        tinta_map, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    threshold = max(int(otsu_thresh) - config.THRESH_C, config.MIN_INK_THRESHOLD)
    _, binary = cv2.threshold(tinta_map, threshold, 255, cv2.THRESH_BINARY)

    ink_pct = 100.0 * np.count_nonzero(binary) / binary.size
    logger.debug(
        f"Binarización ({ink_color}): otsu={otsu_thresh:.0f} "
        f"final={threshold} tinta={ink_pct:.1f}%"
    )

    return binary


def _clean_morphology(binary: np.ndarray) -> np.ndarray:
    """
    Limpieza morfológica: apertura + cierre opcional.
    - Apertura: elimina ruido pequeño sin modificar trazos gruesos.
    - Cierre: conecta trazos separados, rellena espacios pequeños.
    """
    k = max(1, config.MORPH_KERNEL_SIZE)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1))

    # Apertura (elimina ruido)
    result = cv2.morphologyEx(
        binary, cv2.MORPH_OPEN, kernel,
        iterations=config.MORPH_ITERATIONS
    )

    # Cierre opcional (conecta trazos, rellena espacios)
    if config.MORPH_CLOSE_ENABLE:
        result = cv2.morphologyEx(
            result, cv2.MORPH_CLOSE, kernel,
            iterations=config.MORPH_ITERATIONS
        )

    return result


def _remove_straight_lines(binary: np.ndarray) -> np.ndarray:
    """
    Fix D — Elimina líneas rectas impresas (filetes de documento, bordes de
    tabla, subrayados hechos con regla) que quedan cerca de la firma.

    Para cada componente conectado mide, vía PCA sobre sus píxeles:
      - elongación (largo/grosor): una regla supera 60; un trazo de firma ~5,
        y hasta ~30 en un floreo recto. El umbral alto evita falsos positivos.
      - largo absoluto: debe cubrir una fracción grande de la imagen.
      - grosor medio: una regla es fina.
      - orientación del eje principal: las reglas impresas son horizontales o
        verticales; se exige alineación a los ejes para NO tocar trazos
        diagonales de la firma aunque sean rectos.
    Solo se elimina el componente que cumple TODAS las condiciones.
    """
    if not np.any(binary):
        return binary

    H, W = binary.shape[:2]
    long_side = max(H, W)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        binary, connectivity=8
    )
    if num_labels < 2:
        return binary

    dt = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    min_len   = config.LINE_MIN_LEN_RATIO * long_side
    max_thick = config.LINE_MAX_THICK_RATIO * long_side
    tol       = config.LINE_AXIS_TOL_DEG

    to_remove = []
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] < config.MIN_COMPONENT_SIZE:
            continue

        comp = labels == i
        ys, xs = np.where(comp)
        pts = np.column_stack([xs, ys]).astype(np.float32)
        mean = pts.mean(axis=0)
        cov  = np.cov((pts - mean).T)
        evals, evecs = np.linalg.eigh(cov)          # ascendente
        l_small = max(float(evals[0]), 1e-6)
        l_large = max(float(evals[1]), 1e-6)

        elong  = (l_large / l_small) ** 0.5
        length = (l_large ** 0.5) * 4.0
        thick  = float(dt[comp].mean()) * 2.0

        # Ángulo del eje principal respecto de la horizontal (0-180)
        vx, vy = evecs[0, 1], evecs[1, 1]
        ang = abs(np.degrees(np.arctan2(vy, vx))) % 180.0
        axis_aligned = (
            ang < tol or ang > 180.0 - tol or abs(ang - 90.0) < tol
        )

        if (elong >= config.LINE_ELONG_MIN and length >= min_len
                and thick <= max_thick and axis_aligned):
            to_remove.append(i)

    if to_remove:
        binary = binary.copy()
        binary[np.isin(labels, to_remove)] = 0
        logger.debug(
            f"Fix D: {len(to_remove)} línea(s) recta(s) impresa(s) eliminada(s)"
        )
    return binary


def _remove_solid_blobs(binary: np.ndarray) -> np.ndarray:
    """
    Fix C — Elimina manchas/sombras sólidas (sombra de escaneo, borrón pegado
    al borde del papel) que se binarizan como tinta.

    El discriminador clave es el GROSOR MEDIO del componente, medido con el
    distance transform: un trazo de lapicera es fino (pocos px de grosor medio
    aunque la firma sea grande), mientras que una sombra rellena tiene un grosor
    medio mucho mayor (en el Caso 3, 68px vs 14px de la firma). Se exige además
    que el componente toque el borde de la imagen, que es donde aparecen las
    sombras de escaneo, para no tocar nunca un elemento central de la firma.
    """
    if not np.any(binary):
        return binary

    H, W = binary.shape[:2]
    long_side = max(H, W)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        binary, connectivity=8
    )
    if num_labels < 2:
        return binary

    dt = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    thick_thresh = config.BLOB_THICK_RATIO * long_side

    to_remove = []
    for i in range(1, num_labels):
        x, y, bw, bh, area = stats[i]
        if area < config.BLOB_MIN_AREA:
            continue

        comp  = labels == i
        thick = float(dt[comp].mean()) * 2.0
        touches_border = (
            x <= 1 or y <= 1 or (x + bw) >= (W - 1) or (y + bh) >= (H - 1)
        )

        if thick >= thick_thresh and (touches_border or not config.BLOB_REQUIRE_BORDER):
            to_remove.append(i)

    if to_remove:
        binary = binary.copy()
        binary[np.isin(labels, to_remove)] = 0
        logger.debug(
            f"Fix C: {len(to_remove)} mancha(s)/sombra(s) sólida(s) eliminada(s)"
        )
    return binary


def _component_elongation(comp_mask: np.ndarray) -> float:
    """Elongación (largo/grosor) de un componente vía PCA sobre sus píxeles."""
    ys, xs = np.where(comp_mask)
    if xs.size < 2:
        return 1.0
    pts  = np.column_stack([xs, ys]).astype(np.float32)
    cov  = np.cov((pts - pts.mean(axis=0)).T)
    evals = np.linalg.eigvalsh(cov)
    l_small = max(float(evals[0]), 1e-6)
    l_large = max(float(evals[1]), 1e-6)
    return (l_large / l_small) ** 0.5


def _remove_printed_text_block(binary: np.ndarray) -> np.ndarray:
    """
    Fix E — Elimina bloques de TEXTO IMPRESO (nombre, cargo, RUT, etc.) que
    acompañan a la firma, sin tocar los trazos manuscritos.

    No se puede usar la varianza de grosor de trazo: cuando el texto está en
    una fuente cursiva/script, su grosor es tan uniforme y parecido al de la
    firma que ese discriminador falla. Lo que SÍ separa al texto impreso es su
    ESTRUCTURA: varias líneas horizontales paralelas, cada una formada por
    muchos componentes chicos que comparten una misma baseline (borde inferior).
    Una firma manuscrita es diagonal/dispersa y no genera baselines largas.

    Algoritmo:
      1. Toma como "candidatos a carácter" los componentes de tamaño de texto
         (ni los trazos gigantes ni las líneas largas de la firma, excluidos por
         área y elongación).
      2. Vota el borde inferior (baseline) de cada candidato, ponderado por su
         ancho, en un histograma vertical.
      3. Una "línea de texto" es una baseline cuyo ancho acumulado supera una
         fracción del ancho de la imagen. Si hay al menos TEXT_MIN_LINES líneas,
         es un bloque de texto impreso.
      4. Elimina los candidatos que caen sobre una línea detectada. Los trazos
         grandes de la firma quedan protegidos por las guardas de área/elongación
         y nunca se eliminan, aunque crucen el bloque de texto.
    """
    if not np.any(binary):
        return binary

    H, W = binary.shape[:2]
    long_side = max(H, W)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        binary, connectivity=8
    )
    if num_labels < 1 + config.TEXT_MIN_CHARS:
        return binary

    areas = stats[1:, cv2.CC_STAT_AREA]
    a_max = int(areas.max())
    max_char_area = a_max * config.TEXT_MAX_AREA_RATIO
    max_char_h    = config.TEXT_MAX_H_RATIO * long_side

    # 1. Candidatos a carácter (tamaño de texto, no trazos de firma)
    chars = []  # (label, x, y, w, h)
    for i in range(1, num_labels):
        x, y, bw, bh, area = stats[i]
        if area < config.MIN_COMPONENT_SIZE:
            continue
        if area >= max_char_area or bh > max_char_h:
            continue  # trazo grande de la firma → protegido
        if _component_elongation(labels == i) > config.TEXT_MAX_ELONG:
            continue  # trazo largo/fino de la firma → protegido
        chars.append((i, int(x), int(y), int(bw), int(bh)))

    if len(chars) < config.TEXT_MIN_CHARS:
        return binary

    # 2. Agrupar candidatos en líneas por su centro vertical (cy). Se separa en
    #    una línea nueva cuando el salto de cy supera la altura mediana de texto.
    median_h = float(np.median([c[4] for c in chars]))
    chars_sorted = sorted(chars, key=lambda c: c[2] + c[4] / 2.0)
    groups = [[chars_sorted[0]]]
    for c in chars_sorted[1:]:
        cy      = c[2] + c[4] / 2.0
        prev_cy = groups[-1][-1][2] + groups[-1][-1][4] / 2.0
        if cy - prev_cy <= median_h:
            groups[-1].append(c)
        else:
            groups.append([c])

    # 3. Métricas por línea. La PLANITUD de baseline se mide solo con las letras
    #    altas del grupo (las que se apoyan en la baseline), ignorando tildes y
    #    puntos que están más arriba y distorsionarían la medida.
    def line_metrics(g):
        x0     = min(c[1] for c in g)
        x1     = max(c[1] + c[3] for c in g)
        extent = x1 - x0
        max_h  = max(c[4] for c in g)
        tall   = [c for c in g if c[4] >= 0.5 * max_h] or g
        baselines = [c[2] + c[4] for c in tall]
        bl_std = float(np.std(baselines))
        mh     = float(np.median([c[4] for c in tall]))
        return extent, bl_std, mh

    # Una línea es "texto impreso" si es ANCHA (cubre buena parte del ancho) y
    # su baseline es PLANA. Una palabra manuscrita en diagonal tiene baseline
    # inclinada (bl_std alto) y queda descartada.
    text_lines = []  # (group, mh, count)
    for g in groups:
        extent, bl_std, mh = line_metrics(g)
        if (extent >= config.TEXT_LINE_WIDTH_RATIO * W
                and bl_std <= config.TEXT_BASELINE_FLAT_RATIO * mh):
            text_lines.append((g, mh, len(g)))

    # Confirmación del bloque: se exige al menos TEXT_MIN_LINES líneas fuertes
    # (con varios componentes) de altura parecida. Una firma no genera varias
    # líneas planas, anchas y paralelas; un bloque impreso sí.
    strong = [t for t in text_lines if t[2] >= config.TEXT_MIN_CHARS_PER_LINE]
    if len(strong) < config.TEXT_MIN_LINES:
        return binary

    ref_mh = float(np.median([mh for (_g, mh, _n) in strong]))

    # Se eliminan todas las líneas de texto cuya altura concuerda con el bloque
    # (incluye líneas cortas como un "Cargo" de pocas palabras).
    to_remove = []
    n_lines = 0
    for (g, mh, _n) in text_lines:
        if 0.5 * ref_mh <= mh <= 1.8 * ref_mh:
            to_remove.extend(c[0] for c in g)
            n_lines += 1

    if to_remove:
        binary = binary.copy()
        binary[np.isin(labels, to_remove)] = 0
        logger.debug(
            f"Fix E: bloque de texto impreso eliminado "
            f"({n_lines} líneas, {len(to_remove)} componentes)"
        )
    return binary


def _remove_isolated_specks(binary: np.ndarray) -> np.ndarray:
    """
    Retoque final — elimina manchitas/borrones sueltos (bleed-through, marcas de
    lapicera aisladas) que sobreviven al resto del pipeline.

    Un speck de ruido cumple dos cosas a la vez: es chico respecto del cuerpo de
    la firma Y está separado de ella. Los detalles legítimos de una firma (punto
    de la i, tilde, parafa corta) son chicos pero están PEGADOS o muy cerca del
    cuerpo. Por eso el filtro exige área pequeña relativa al componente mayor Y
    un gap grande hasta él; así nunca borra partes reales de la firma.
    """
    if not np.any(binary):
        return binary

    H, W = binary.shape[:2]
    long_side = max(H, W)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        binary, connectivity=8
    )
    if num_labels < 3:
        return binary

    areas    = stats[1:, cv2.CC_STAT_AREA]
    largest  = int(np.argmax(areas)) + 1
    a_max    = int(areas[largest - 1])
    max_area = a_max * config.SPECK_MAX_AREA_RATIO
    min_gap  = config.SPECK_MIN_GAP_RATIO * long_side

    # Distancia de cada píxel al componente mayor (cuerpo de la firma)
    inv = (labels != largest).astype(np.uint8)
    dist_to_main = cv2.distanceTransform(inv, cv2.DIST_L2, 5)

    to_remove = []
    for i in range(1, num_labels):
        if i == largest:
            continue
        if stats[i, cv2.CC_STAT_AREA] >= max_area:
            continue
        comp = labels == i
        if float(dist_to_main[comp].min()) >= min_gap:
            to_remove.append(i)

    if to_remove:
        binary = binary.copy()
        binary[np.isin(labels, to_remove)] = 0
        logger.debug(
            f"Retoque: {len(to_remove)} manchita(s) aislada(s) eliminada(s)"
        )
    return binary


def _isolate_main_cluster(binary: np.ndarray) -> np.ndarray:
    """
    Aísla los clusters significativos de tinta y descarta cualquier marca
    lejana de tamaño pequeño (logos de CamScanner, sellos de esquina,
    marcas de agua, foliado).

    Estrategia:
      1. Dilata la binaria con un kernel proporcional al tamaño de imagen.
         Eso conecta componentes cercanos entre sí (letras de una misma
         palabra, palabras adyacentes) sin llegar a unir cosas en partes
         opuestas de la página.
      2. Encuentra todos los componentes conectados en la versión dilatada.
      3. Conserva el más grande Y todos los demás cuya área sea al menos
         CLUSTER_MIN_AREA_RATIO del más grande. Una firma de dos o tres
         palabras genera clusters comparables en tamaño; un logo de
         escáner siempre es mucho más chico que la firma.

    Esto cubre los dos casos a la vez:
      - Si las palabras se conectan en uno solo (gap < kernel): un cluster
        grande con todo.
      - Si quedan separadas (gap > kernel): varios clusters comparables;
        el filtro de área los mantiene todos. Solo cae lo realmente chico
        (footer del escáner, foliado, etc.).
    """
    if not np.any(binary):
        return binary

    H, W = binary.shape[:2]
    k = max(15, int(max(H, W) * config.CLUSTER_DILATION_RATIO))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))

    dilated = cv2.dilate(binary, kernel, iterations=1)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        dilated, connectivity=8
    )
    if num_labels < 2:
        return binary

    # Áreas de cada cluster (en la versión dilatada), excluyendo el fondo
    areas = stats[1:, cv2.CC_STAT_AREA]
    max_area = int(areas.max())
    min_keep_area = int(max_area * config.CLUSTER_MIN_AREA_RATIO)

    keep_labels = [
        i + 1 for i, area in enumerate(areas) if int(area) >= min_keep_area
    ]

    mask = np.isin(labels, keep_labels).astype(np.uint8) * 255
    result = cv2.bitwise_and(binary, binary, mask=mask)

    before = int(np.count_nonzero(binary))
    after  = int(np.count_nonzero(result))
    discarded = before - after
    if discarded > 0:
        logger.debug(
            f"Aislamiento: kernel={k}px, {len(keep_labels)}/{num_labels-1} clusters "
            f"conservados (área >= {min_keep_area}px), {discarded} px de tinta lejana descartados"
        )
    return result


def _remove_artifacts(binary: np.ndarray) -> np.ndarray:
    """
    Elimina componentes conectados pequeños (ruido residual).
    Después del morphological closing, solo quedan los artefactos muy pequeños.
    """
    result = binary.copy()

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        result, connectivity=8
    )

    if num_labels < 2:
        return result

    logger.debug(f"_remove_artifacts: {num_labels - 1} componentes detectados")

    artifacts_to_remove = []

    for label in range(1, num_labels):
        area = stats[label, 4]
        width = stats[label, 2]
        height = stats[label, 3]

        # Criterio 1: Muy pequeño (ruido residual)
        if area < config.MIN_COMPONENT_SIZE:
            artifacts_to_remove.append(label)
            continue

        # Criterio 2: Línea muy delgada
        is_thin_line = (width < config.MIN_COMPONENT_WIDTH and height >= 10) or \
                       (height < config.MIN_COMPONENT_HEIGHT and width >= 10)
        if is_thin_line:
            artifacts_to_remove.append(label)

    if artifacts_to_remove:
        artifacts_mask = np.isin(labels, artifacts_to_remove)
        result[artifacts_mask] = 0

    logger.debug(
        f"Limpieza de artefactos: {len(artifacts_to_remove)} componentes eliminados"
    )

    return result


def _find_signature_bbox(binary: np.ndarray) -> tuple[int, int, int, int] | None:
    """
    Busca el bounding-box mínimo que engloba los contornos significativos,
    filtrando puntos de ruido alejados. Estrategia:
      1. Encontrar contornos con área >= MIN_SIGNATURE_AREA
      2. Calcular centroide del grupo principal
      3. Filtrar contornos que estén muy alejados (ruido aislado)

    Returns:
        (x, y, w, h) del rectángulo, o None si no se detectó nada.
    """
    contours, _ = cv2.findContours(
        binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        return None

    # Intentar primero con contornos significativos
    significant = [
        c for c in contours
        if cv2.contourArea(c) >= config.MIN_SIGNATURE_AREA
    ]

    # Si no hay contornos significativos, usar todos con área > 30 px²
    if not significant:
        significant = [c for c in contours if cv2.contourArea(c) >= 30]

    if not significant:
        return None

    # Calcular bounding-boxes y centroides
    bboxes = [cv2.boundingRect(c) for c in significant]
    centroids = []
    for x, y, w, h in bboxes:
        cx, cy = x + w // 2, y + h // 2
        centroids.append((cx, cy))

    # Encontrar el centroide promedio (la firma principal)
    avg_x = sum(cx for cx, cy in centroids) / len(centroids)
    avg_y = sum(cy for cx, cy in centroids) / len(centroids)

    # Filtra contornos demasiado lejos del centroide promedio (ruido aislado).
    # La distancia escala con el tamaño de la imagen: una firma en un PDF de
    # CamScanner a 300 DPI mide ~2500px de ancho y sus partes (nombre, apellido,
    # parafa) pueden estar a >1500px del centro. Un valor fijo deja afuera
    # palabras enteras. Usamos MAX_CENTROID_DISTANCE como piso mínimo.
    H, W = binary.shape[:2]
    max_distance = max(
        config.MAX_CENTROID_DISTANCE,
        int(max(W, H) * config.CENTROID_DISTANCE_RATIO),
    )
    filtered_bboxes = [
        bbox for bbox, (cx, cy) in zip(bboxes, centroids)
        if ((cx - avg_x) ** 2 + (cy - avg_y) ** 2) ** 0.5 <= max_distance
    ]

    if not filtered_bboxes:
        filtered_bboxes = bboxes  # Fallback: usar todos si el filtro fue muy agresivo

    # Unir todos los bounding-boxes filtrados
    xs, ys, ws, hs = zip(*filtered_bboxes)
    x1 = min(xs)
    y1 = min(ys)
    x2 = max(x + w for x, w in zip(xs, ws))
    y2 = max(y + h for y, h in zip(ys, hs))

    return x1, y1, x2 - x1, y2 - y1


def _add_padding(
    x: int, y: int, w: int, h: int, img_shape: tuple
) -> tuple[int, int, int, int]:
    """Expande el recorte añadiendo padding sin salirse de los límites."""
    H, W = img_shape[:2]
    pad  = config.PADDING_PX
    x1   = max(0, x - pad)
    y1   = max(0, y - pad)
    x2   = min(W, x + w + pad)
    y2   = min(H, y + h + pad)
    return x1, y1, x2, y2


def _build_soft_mask(binary_crop: np.ndarray) -> np.ndarray:
    """
    Genera máscara alfa inteligente: suaviza bordes EXTERNOS sin dañar interiores.
    Usa edge detection + dilation selectiva para preservar huecos internos.
    """
    # binary_crop: firma=blanco(255), fondo=negro(0)
    mask_int = binary_crop.astype(np.uint8)

    # Paso 1: Detectar bordes de la firma (transiciones blanco→negro)
    edges = cv2.Canny(
        mask_int,
        config.EDGE_DETECTION_THRESHOLD1,
        config.EDGE_DETECTION_THRESHOLD2
    )

    # Paso 2: Dilatar bordes levemente para crear zona de transición
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    edges_dilated = cv2.dilate(edges, kernel, iterations=1)

    # Paso 3: Suavizar zona de bordes
    edge_zone = cv2.GaussianBlur(
        edges_dilated.astype(np.float32), (5, 5), 1.0
    ) / 255.0

    # Paso 4: Crear máscara suave solo en bordes, interior firme
    mask_float = mask_int.astype(np.float32) / 255.0
    interior_mask = (mask_int == 255).astype(np.float32)

    # Interior puro (255) + bordes suavizados
    mask_soft = interior_mask + (1.0 - interior_mask) * (
        mask_float * edge_zone * config.EDGE_SMOOTH_AMOUNT
    )

    return (np.clip(mask_soft, 0, 1) * 255).astype(np.uint8)


def _colorize_signature(alpha_mask: np.ndarray) -> np.ndarray:
    """
    Genera un PNG RGBA donde:
      - Los canales R, G, B son todos 0 (negro puro).
      - El canal A proviene de la máscara suave (opacidad de la firma).
    El fondo queda completamente transparente (A=0).
    """
    H, W   = alpha_mask.shape
    r, g, b = config.SIGNATURE_COLOR  # (0, 0, 0)

    rgba = np.zeros((H, W, 4), dtype=np.uint8)
    rgba[:, :, 0] = r
    rgba[:, :, 1] = g
    rgba[:, :, 2] = b
    rgba[:, :, 3] = alpha_mask  # transparencia real

    return rgba


def _scale_to_output(rgba: np.ndarray) -> np.ndarray:
    """
    Escala la imagen al tamaño de salida configurado si el lado más largo
    es menor que OUTPUT_LONG_SIDE_PX. No reduce imágenes que ya son grandes.
    Utiliza interpolación Lanczos para máxima calidad.
    """
    H, W     = rgba.shape[:2]
    long_side = max(H, W)
    target    = config.OUTPUT_LONG_SIDE_PX

    if long_side >= target:
        return rgba  # ya tiene suficiente resolución

    scale  = target / long_side
    new_W  = int(W * scale)
    new_H  = int(H * scale)

    return cv2.resize(rgba, (new_W, new_H), interpolation=cv2.INTER_LANCZOS4)


def _sharpen(rgba: np.ndarray) -> np.ndarray:
    """
    Unsharp mask sobre los canales RGB (no sobre alfa) para realzar
    los bordes finos de los trazos de la firma.
    """
    rgb    = rgba[:, :, :3].astype(np.float32)
    blur   = cv2.GaussianBlur(rgb, (0, 0), sigmaX=2.0)
    amount = config.SHARPEN_KERNEL_AMOUNT
    sharp  = cv2.addWeighted(rgb, 1.0 + amount, blur, -amount, 0)
    sharp  = np.clip(sharp, 0, 255).astype(np.uint8)

    result         = rgba.copy()
    result[:, :, :3] = sharp
    return result


# ---------------------------------------------------------------------------
# Función principal del módulo
# ---------------------------------------------------------------------------

def process_signature(input_path: str, output_path: str) -> None:
    """
    Ejecuta el pipeline completo para un único archivo de firma.

    Args:
        input_path:  Ruta al archivo de entrada (PDF/JPG/JPEG/PNG).
        output_path: Ruta donde se guardará el PNG con transparencia.

    Raises:
        FileNotFoundError: Si el archivo de entrada no existe.
        ValueError: Si la imagen no contiene una firma detectable.
        RuntimeError: Para cualquier otro error durante el procesamiento.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"No se encontró el archivo: {input_path}")

    ext = os.path.splitext(input_path)[1].lower()

    # ---- 1. Carga de imagen ------------------------------------------------
    if ext == ".pdf":
        from pdf_converter import pdf_to_image
        bgr = pdf_to_image(input_path)
    elif ext in {".docx", ".doc"}:
        from docx_converter import get_first_signature_from_docx
        bgr = get_first_signature_from_docx(input_path)
    else:
        # IMREAD_UNCHANGED preserva el canal alfa si existe; _flatten_to_bgr lo
        # compone sobre blanco. Con IMREAD_COLOR los PNG transparentes se
        # aplanaban sobre negro y rompían la binarización por completo.
        raw = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
        if raw is None:
            raise RuntimeError(
                f"OpenCV no pudo leer la imagen: '{input_path}'. "
                "Verifique que el archivo no esté corrupto."
            )
        bgr = _flatten_to_bgr(raw)

    logger.debug(f"Imagen cargada: {bgr.shape[1]}x{bgr.shape[0]} px")

    # ---- 1.4. Normalización de resolución de trabajo ------------------------
    # Sube la resolución de imágenes pequeñas para que el grosor de trazo entre
    # en el rango calibrado del pipeline (evita la sobre-erosión de trazos finos).
    bgr = _normalize_resolution(bgr)

    # ---- 1.5. Remover footer de escáner (CamScanner, etc.) ------------------
    bgr = _remove_scanner_footer(bgr)

    # ---- 2. Corrección de iluminación --------------------------------------
    bgr_corrected = _correct_illumination(bgr)

    # ---- 3. Detección automática de color de tinta -------------------------
    ink_color = _detect_ink_color(bgr_corrected)

    # ---- 4. Extracción del canal con mejor contraste para esa tinta -------
    # Azul → saturación HSV, Negra → canal R invertido.
    # Esto separa la firma del fondo MUCHO mejor que escala de grises cuando
    # el papel tiene tonos parecidos a la tinta.
    tinta_map = _extract_ink_channel(bgr_corrected, ink_color)

    # ---- 5. Eliminación de ruido sobre el mapa de tinta -------------------
    tinta_clean = _denoise_tinta_map(tinta_map)

    # ---- 6. Binarización (Otsu sobre mapa de tinta) -----------------------
    binary = _binarize(tinta_clean, ink_color)

    # ---- 7. Limpieza morfológica -------------------------------------------
    binary_clean = _clean_morphology(binary)

    # ---- 8. Eliminación de artefactos y ruido ----------------------------
    binary_clean = _remove_artifacts(binary_clean)

    # ---- 8.5. Fix D: descartar líneas rectas impresas (filetes/bordes) ----
    binary_clean = _remove_straight_lines(binary_clean)

    # ---- 8.6. Fix C: descartar manchas/sombras sólidas pegadas al borde ---
    binary_clean = _remove_solid_blobs(binary_clean)

    # ---- 8.7. Fix E: descartar bloque de texto impreso (nombre/cargo/RUT) --
    # DESACTIVADO. La detección geométrica (baselines paralelas) no es confiable
    # cuando el texto impreso usa una fuente cursiva/script y se SOLAPA con la
    # firma: las palabras de texto fusionadas en un componente grande quedan
    # protegidas (texto residual) mientras que bits chicos de la firma se
    # confunden con texto y se borran (firma mutilada). Se deja la función
    # _remove_printed_text_block disponible pero fuera del pipeline hasta tener
    # un método robusto (p. ej. detector de texto por OCR/ML). Ver roadmap.
    # binary_clean = _remove_printed_text_block(binary_clean)

    # ---- 9. Aislar cluster principal (descarta logos/sellos/marcas) -----
    # Conecta partes cercanas de la firma entre sí y descarta cualquier
    # tinta espacialmente aislada (logo de CamScanner, sello en esquina,
    # foliado del documento, etc.). Esto es más confiable que la detección
    # de footer por línea horizontal, que falla cuando el escáner no
    # imprime divisoria visible.
    binary_clean = _isolate_main_cluster(binary_clean)

    # ---- 9.5. Retoque: quitar manchitas aisladas (bleed-through, borrones) -
    binary_clean = _remove_isolated_specks(binary_clean)

    # ---- 10. Detección del bounding-box de la firma -----------------------
    bbox = _find_signature_bbox(binary_clean)
    if bbox is None:
        raise ValueError(
            "No se detectó ninguna firma en la imagen. "
            "Verifique que el archivo contenga trazos visibles."
        )

    x, y, w, h = bbox
    logger.debug(f"Firma detectada en: x={x}, y={y}, w={w}, h={h}")

    # ---- 10. Recorte con padding -------------------------------------------
    x1, y1, x2, y2 = _add_padding(x, y, w, h, binary_clean.shape)
    binary_crop     = binary_clean[y1:y2, x1:x2]

    # ---- 11. Máscara suave (bordes anti-aliasing) --------------------------
    soft_mask = _build_soft_mask(binary_crop)

    # ---- 12. Canal RGBA con negro puro y transparencia ---------------------
    rgba = _colorize_signature(soft_mask)

    # ---- 13. Escalado al tamaño de salida ----------------------------------
    rgba_scaled = _scale_to_output(rgba)

    # ---- 14. Nitidez final -------------------------------------------------
    rgba_sharp = _sharpen(rgba_scaled)

    # ---- 15. Guardar PNG con transparencia --------------------------------
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # cv2.imwrite con PNG preserva el canal alfa automáticamente
    success = cv2.imwrite(output_path, rgba_sharp)
    if not success:
        raise RuntimeError(f"No se pudo guardar el archivo: '{output_path}'")

    logger.debug(
        f"PNG guardado: {rgba_sharp.shape[1]}x{rgba_sharp.shape[0]} px → {output_path}"
    )
