"""
config.py — Configuración global del proyecto de procesamiento de firmas.

Centraliza todos los parámetros ajustables para facilitar el mantenimiento
y la adaptación a distintos lotes de documentos sin tocar el código principal.
"""

import os

# ---------------------------------------------------------------------------
# Rutas de carpetas
# ---------------------------------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR  = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
LOG_DIR    = os.path.join(BASE_DIR, "logs")

# ---------------------------------------------------------------------------
# Formatos de entrada aceptados
# ---------------------------------------------------------------------------
SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".doc"}

# ---------------------------------------------------------------------------
# Conversión de PDF
# ---------------------------------------------------------------------------
PDF_DPI = 300          # Resolución al rasterizar la primera página del PDF

# ---------------------------------------------------------------------------
# Pipeline de limpieza de imagen
# ---------------------------------------------------------------------------

# Normalización de resolución de trabajo
# El resto de los parámetros del pipeline (kernel morfológico, áreas mínimas en
# px²) están calibrados para escaneos de alta resolución (~2500px, tipo
# CamScanner). En imágenes pequeñas (PNG exportados, firmas embebidas en docx,
# screenshots) el trazo mide pocos píxeles y la apertura 3x3 + el filtro de
# componentes los destruyen. Subir el lado largo hasta este valor devuelve el
# grosor de trazo al rango donde esos parámetros son seguros. Solo se escala
# HACIA ARRIBA: las imágenes grandes (el caso que ya funciona bien) no se tocan.
WORK_LONG_SIDE_PX = 2000

# Corrección de iluminación (CLAHE)
CLAHE_CLIP_LIMIT    = 2.0    # Límite de amplificación de contraste local
CLAHE_TILE_GRID     = (8, 8) # Tamaño de la cuadrícula de tiles

# Detección automática de color de tinta (azul vs negra)
BLUE_INK_HUE_MIN    = 90     # Hue mínimo (HSV 0-179) para considerar píxel azul
BLUE_INK_HUE_MAX    = 140    # Hue máximo (HSV) para considerar píxel azul
BLUE_INK_MIN_SAT    = 30     # Saturación mínima para tinta azul real
DARK_PIXEL_MAX_GRAY = 150    # Píxeles con gray < este valor se consideran "oscuros"
BLUE_INK_RATIO      = 0.30   # Si >30% de oscuros son azules → tinta AZUL, si no NEGRA

# Eliminación de ruido (NLM sobre mapa de tinta)
DENOISE_H           = 16     # Fuerza del denoising
DENOISE_TEMPLATE_WS = 7      # Tamaño de ventana de plantilla
DENOISE_SEARCH_WS   = 21     # Tamaño de ventana de búsqueda

# Binarización (Otsu sobre mapa de tinta + margen para trazos finos)
THRESH_C            = 15     # Margen restado del corte Otsu (sube = capta más; baja = más limpio)
MIN_INK_THRESHOLD   = 25     # Piso absoluto del umbral (evita tomar ruido cuando el Otsu es muy bajo)

# Morfología (apertura solamente)
MORPH_KERNEL_SIZE   = 1          # 1 = 3x3 kernel
MORPH_ITERATIONS    = 1          # 1 iteración
MORPH_CLOSE_ENABLE  = False      # Cierre deshabilitado por defecto

# Eliminación de artefactos por componentes conectados
MIN_COMPONENT_HEIGHT = 2         # Altura mínima permitida
MIN_COMPONENT_WIDTH  = 2         # Ancho mínimo permitido
MIN_COMPONENT_SIZE   = 95        # Área mínima (px²) para no considerar ruido residual

# Fix D — Eliminación de líneas rectas impresas (filetes, bordes, subrayados de regla)
# Una regla impresa es un componente larguísimo, finísimo y alineado a los ejes.
# Se separa nítido de los trazos de firma (elongación ≤ ~5; un floreo recto de
# firma llega a ~30). El umbral 60 + la exigencia de estar alineada a H/V evita
# tocar trazos diagonales de la firma.
LINE_ELONG_MIN       = 60.0   # Elongación PCA mínima (largo/grosor) para considerar "línea"
LINE_MIN_LEN_RATIO   = 0.25   # Largo mínimo como fracción del lado largo de la imagen
LINE_MAX_THICK_RATIO = 0.012  # Grosor medio máximo (fracción del lado largo): una regla es fina
LINE_AXIS_TOL_DEG    = 12.0   # Tolerancia a horizontal/vertical en grados (las reglas son axis-aligned)

# Fix C — Eliminación de manchas/sombras sólidas (sombra de escaneo, borrón de borde)
# Un trazo de lapicera nunca tiene un grosor medio grande; una sombra rellena sí
# (en el Caso 3 medía 68px de grosor medio vs 14px de la firma). Se exige además
# que toque el borde de la imagen, que es donde caen las sombras de escaneo.
BLOB_THICK_RATIO     = 0.015  # Grosor medio (fracción del lado largo) sobre el cual es "masa rellena", no trazo
BLOB_MIN_AREA        = 2000   # Área mínima (px²) para que el filtro actúe (no toca detalles chicos)
BLOB_REQUIRE_BORDER  = True   # Solo eliminar si el componente toca el borde de la imagen

# Fix E — Eliminación de bloque de TEXTO IMPRESO (nombre/cargo/RUT bajo la firma)
# No se usa varianza de grosor (en fuentes cursivas el texto tiene el mismo grosor
# que la firma). Se detecta la ESTRUCTURA: varias baselines horizontales paralelas
# formadas por muchos componentes chicos. Las guardas de área y elongación protegen
# los trazos grandes de la firma, que nunca se eliminan aunque crucen el texto.
TEXT_MAX_AREA_RATIO     = 0.20  # Un candidato a carácter mide < 20% del componente mayor
TEXT_MAX_H_RATIO        = 0.12  # Altura máx de un carácter como fracción del lado largo
TEXT_MAX_ELONG          = 6.0   # Elongación máx (excluye trazos largos/finos de la firma)
TEXT_MIN_CHARS          = 6     # Mínimo de candidatos para evaluar bloque de texto
TEXT_LINE_WIDTH_RATIO   = 0.30  # Extensión horizontal mínima de una línea (fracción del ancho)
TEXT_BASELINE_FLAT_RATIO= 0.6   # Planitud: std de baseline <= este factor * altura de letra
TEXT_MIN_CHARS_PER_LINE = 3     # Mínimo de componentes para que una línea sea "fuerte"
TEXT_MIN_LINES          = 2     # Mínimo de líneas fuertes paralelas para confirmar el bloque

# Retoque final — eliminación de manchitas aisladas (bleed-through, borrones sueltos)
SPECK_MAX_AREA_RATIO  = 0.015 # Una manchita mide < 1.5% del cuerpo de la firma
SPECK_MIN_GAP_RATIO   = 0.04  # Y está a > 4% del lado largo de distancia del cuerpo

# Aislamiento del cluster principal (descarta logos/sellos espacialmente aislados)
CLUSTER_DILATION_RATIO   = 0.08 # Fracción del lado largo usada como kernel de dilatación. 0.08 ≈ 200px en imagen 2500x. Une palabras separadas y huecos dentro de una palabra; no alcanza al footer típico (200-500px del cuerpo).
CLUSTER_MIN_AREA_RATIO   = 0.15 # Área mínima de cada cluster como fracción del cluster más grande. Con 0.15, una palabra suelta de la firma se mantiene siempre que mida ≥15% del cluster principal. El footer de un escáner casi siempre es menor a eso.

# Detección del bounding-box de la firma
MIN_SIGNATURE_AREA       = 180  # Área mínima de contorno para considerarse parte de la firma (px²)
MAX_CENTROID_DISTANCE    = 800  # Distancia máxima absoluta (px) al centroide promedio — piso mínimo del filtro
CENTROID_DISTANCE_RATIO  = 0.55 # Distancia máxima como fracción del lado largo de la imagen. Con 0.55 una firma puede ocupar todo el ancho útil sin que se filtren los extremos.

# ---------------------------------------------------------------------------
# Post-procesamiento
# ---------------------------------------------------------------------------
PADDING_PX          = 30    # Píxeles de margen alrededor del recorte final

# Máscara inteligente (edge-aware)
EDGE_DETECTION_THRESHOLD1 = 50    # Canny threshold bajo
EDGE_DETECTION_THRESHOLD2 = 150   # Canny threshold alto
EDGE_SMOOTH_AMOUNT = 0.3          # Factor de suavizado en bordes (0.0-1.0)

# Escala de salida (px del lado largo para uso en certificados)
OUTPUT_LONG_SIDE_PX = 1200  # Si la firma es más pequeña, se escala hasta este valor

# Nitidez (unsharp mask)
SHARPEN_KERNEL_AMOUNT = 2.2  # Factor de realce de bordes (más nitidez)

# Color de la firma en el PNG final (negro puro)
SIGNATURE_COLOR = (0, 0, 0)  # RGB

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILENAME = "procesamiento.log"
