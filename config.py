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
CLAHE_CLIP_LIMIT    = 2.0   # Límite de amplificación de contraste local
CLAHE_TILE_GRID     = (8, 8) # Tamaño de la cuadrícula de tiles

# Detección de tinta basada en color (HSV + LAB)
TINTA_MAX_LIGHTNESS = 130   # Valor LAB L máximo para tinta (0-255, menor = más oscuro)
TINTA_MIN_SATURATION = 5    # Saturación HSV mínima (0-255)
COLOR_DISTANCE_THRESHOLD = 30  # Distancia máxima en espacio LAB para color

# Eliminación de ruido (NLM sobre mapa de tinta óptimo)
DENOISE_H           = 16    # Fuerza del denoising
DENOISE_TEMPLATE_WS = 7     # Tamaño de ventana de plantilla
DENOISE_SEARCH_WS   = 21    # Tamaño de ventana de búsqueda

# Umbralización (balance conservador)
THRESH_BLOCK_SIZE   = 51    # Bloque grande = ignora ruido local
THRESH_C            = 18    # Detecta tinta débil sin capturar demasiado ruido
BINARIZE_CLAHE_CLIP = 3.0   # Clip limit para CLAHE pre-binarización
BINARIZE_CLAHE_GRID = (8, 8) # Grid size para CLAHE

# Morfología (apertura solamente)
MORPH_KERNEL_SIZE   = 1          # 1 = 3x3 kernel
MORPH_ITERATIONS    = 1          # 1 iteración
MORPH_CLOSE_ENABLE  = False      # Cierre deshabilitado

# Eliminación de artefactos por componentes conectados (agresivo con ruido de escaneo)
MIN_COMPONENT_HEIGHT   = 2       # Altura mínima (muy pequeño)
MIN_COMPONENT_WIDTH    = 2       # Ancho mínimo (muy pequeño)
MIN_COMPONENT_DENSITY  = 0.10    # Densidad mínima muy baja (permite detalles)
MIN_COMPONENT_SIZE     = 95      # Elimina ruido residual, preserva firma

# DESACTIVADO: Relleno de huecos (NO reconstruir espacios internos)
# Prioridad: Eliminar artefactos, no rellenar espacios

# Contorno / detección de firma
MIN_SIGNATURE_AREA  = 180   # Área mínima de contorno para considerarse firma (px²)

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
