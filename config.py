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
