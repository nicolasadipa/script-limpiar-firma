"""
pdf_converter.py — Conversión de la primera página de un PDF a imagen NumPy.

Utiliza PyMuPDF (fitz) para rasterizar el PDF con la resolución configurada
en config.PDF_DPI y devolver un array BGR compatible con OpenCV.
"""

import numpy as np
import fitz  # PyMuPDF

import config
from logger import setup_logger

logger = setup_logger()


def pdf_to_image(pdf_path: str) -> np.ndarray:
    """
    Convierte la primera página de un PDF en un array NumPy BGR.

    Args:
        pdf_path: Ruta absoluta al archivo PDF.

    Returns:
        Array NumPy con forma (H, W, 3) en espacio de color BGR.

    Raises:
        ValueError: Si el PDF no tiene páginas.
        RuntimeError: Si PyMuPDF no puede abrir el archivo.
    """
    logger.debug(f"Abriendo PDF: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise RuntimeError(f"PyMuPDF no pudo abrir '{pdf_path}': {exc}") from exc

    if doc.page_count == 0:
        doc.close()
        raise ValueError(f"El PDF '{pdf_path}' no contiene páginas.")

    page = doc[0]

    # Calcular matriz de transformación según el DPI deseado
    # PyMuPDF usa 72 dpi como base → factor = target_dpi / 72
    zoom   = config.PDF_DPI / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    # Rasterizar la página como imagen RGB (sin canal alfa por defecto)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    doc.close()

    # Convertir el pixmap a array NumPy en formato RGB
    img_rgb = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, 3
    )

    # OpenCV trabaja en BGR → invertir canales
    img_bgr = img_rgb[:, :, ::-1].copy()

    logger.debug(
        f"PDF convertido a imagen {img_bgr.shape[1]}x{img_bgr.shape[0]} px "
        f"a {config.PDF_DPI} dpi."
    )
    return img_bgr
