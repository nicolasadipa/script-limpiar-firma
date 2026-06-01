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

def _remove_scanner_footer(bgr: np.ndarray) -> np.ndarray:
    """
    Detecta y elimina región inferior con logo de escáner (CamScanner, etc.).
    """
    H, W = bgr.shape[:2]

    if H < 300:
        return bgr

    # Remover últimos 80 píxeles (donde va el logo CamScanner)
    cutoff_px = min(80, H // 12)
    bgr_cropped = bgr[:H - cutoff_px, :]

    logger.debug(f"Footer removido: {H}px → {H - cutoff_px}px")
    return bgr_cropped


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

    Analiza los píxeles oscuros y cuenta cuántos son azules.
    Si > 30% de píxeles oscuros son azules → AZUL
    Si < 30% → NEGRA

    Returns: "blue" o "black"
    """
    hsv = cv2.cvtColor(bgr_corrected, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(bgr_corrected, cv2.COLOR_BGR2GRAY)

    h, s, v = cv2.split(hsv)

    # Detectar píxeles oscuros (potencial tinta)
    mask_dark = gray < 150

    # Detectar píxeles azules oscuros (H: 90-140, S > 30)
    mask_blue_ink = (h >= 90) & (h <= 140) & (s > 30) & mask_dark

    # Calcular proporción de azul en píxeles oscuros
    dark_count = np.sum(mask_dark)
    blue_count = np.sum(mask_blue_ink)

    if dark_count > 0:
        blue_ratio = blue_count / dark_count
    else:
        blue_ratio = 0

    logger.debug(f"Detección de color: azul={blue_ratio:.1%}, oscuros={dark_count}")

    # Decidir: si más del 30% son azules → es azul
    ink_color = "blue" if blue_ratio > 0.30 else "black"
    logger.info(f"Tinta detectada: {ink_color.upper()}")

    return ink_color


# Funciones de binarización antiguas removidas - ahora usamos mapa de tinta optimizado




def _binarize(tinta_map: np.ndarray, ink_color: str) -> np.ndarray:
    """
    Binarización simple y limpia sobre el mapa de tinta óptimo.

    El mapa de tinta ya tiene:
    - Firma resaltada (blanco/255)
    - Ruido atenuado (por bilateral filter)
    - Bordes preservados (no borrados por suavizado)

    Solo aplicamos threshold adaptativo sobre esta base limpia.

    Resultado: firma=blanco(255), fondo=negro(0)
    """
    logger.debug(f"Binarizando con canal óptimo para tinta {ink_color.upper()}...")

    binary = cv2.adaptiveThreshold(
        tinta_map,
        maxValue=255,
        adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        thresholdType=cv2.THRESH_BINARY,
        blockSize=config.THRESH_BLOCK_SIZE,
        C=config.THRESH_C,
    )

    # Invertir: firma=blanco(255), fondo=negro(0)
    binary_inverted = cv2.bitwise_not(binary)

    logger.debug(
        f"Binarización: {np.sum(binary_inverted > 0)} píxeles de tinta "
        f"({100*np.sum(binary_inverted > 0)/(tinta_map.shape[0]*tinta_map.shape[1]):.1f}% de imagen)"
    )

    return binary_inverted


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

    # Filtrar contornos que estén a más de 800 px de distancia del centroide promedio
    # (mantiene toda la firma incluso si está dispersa)
    max_distance = 800
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
        bgr = cv2.imread(input_path, cv2.IMREAD_COLOR)
        if bgr is None:
            raise RuntimeError(
                f"OpenCV no pudo leer la imagen: '{input_path}'. "
                "Verifique que el archivo no esté corrupto."
            )

    logger.debug(f"Imagen cargada: {bgr.shape[1]}x{bgr.shape[0]} px")

    # ---- 1.5. Remover footer de escáner (CamScanner, etc.) ------------------
    bgr = _remove_scanner_footer(bgr)

    # ---- 2. Corrección de iluminación --------------------------------------
    bgr_corrected = _correct_illumination(bgr)

    # ---- 3. Escala de grises -----------------------------------------------
    gray = cv2.cvtColor(bgr_corrected, cv2.COLOR_BGR2GRAY)

    # ---- 4. Eliminación de ruido -------------------------------------------
    gray_clean = cv2.fastNlMeansDenoising(
        gray,
        h=config.DENOISE_H,
        templateWindowSize=config.DENOISE_TEMPLATE_WS,
        searchWindowSize=config.DENOISE_SEARCH_WS,
    )

    # ---- 5. Binarización ---------------------------------------------------
    binary = cv2.adaptiveThreshold(
        gray_clean,
        maxValue=255,
        adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        thresholdType=cv2.THRESH_BINARY,
        blockSize=config.THRESH_BLOCK_SIZE,
        C=config.THRESH_C,
    )
    binary = cv2.bitwise_not(binary)

    # ---- 7. Limpieza morfológica -------------------------------------------
    binary_clean = _clean_morphology(binary)

    # ---- 8. Eliminación de artefactos y ruido ----------------------------
    binary_clean = _remove_artifacts(binary_clean)

    # ---- 9. Detección del bounding-box de la firma -------------------------
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
