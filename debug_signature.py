"""
debug_signature.py — Procesa UNA firma y guarda cada paso del pipeline como imagen.
Útil para diagnosticar dónde se pierde la firma.
"""

import os
import sys
import cv2
import numpy as np

import config
from logger import setup_logger
from processor import (
    _correct_illumination,
    _to_gray,
    _denoise,
    _detect_ink_color,
    _binarize,
    _clean_morphology,
    _remove_artifacts,
    _find_signature_bbox,
    _add_padding,
)
from pdf_converter import pdf_to_image

logger = setup_logger()

DEBUG_DIR = os.path.join(config.BASE_DIR, "debug_output")


def save_debug_image(name: str, img: np.ndarray) -> None:
    """Guarda una imagen de debug con información."""
    os.makedirs(DEBUG_DIR, exist_ok=True)

    # Normalizar para visualización
    if img.max() > 1:
        # Imagen uint8
        display = img
    else:
        # Imagen float [0, 1]
        display = (img * 255).astype(np.uint8)

    path = os.path.join(DEBUG_DIR, name)
    cv2.imwrite(path, display)
    print(f"  DEBUG: {name} → {path}")


def debug_signature(pdf_path: str) -> None:
    """Procesa una firma con debug completo."""
    print(f"\n=== DEBUG SIGNATURE ===")
    print(f"Input: {pdf_path}\n")

    # 1. Cargar
    print("1. Cargando PDF...")
    bgr = pdf_to_image(pdf_path)
    save_debug_image("01_original.png", bgr)
    print(f"   Dimensiones: {bgr.shape}")

    # 2. Corrección de iluminación
    print("\n2. Corrigiendo iluminación (CLAHE)...")
    bgr_corrected = _correct_illumination(bgr)
    save_debug_image("02_after_clahe.png", bgr_corrected)

    # 3. Escala de grises
    print("\n3. Convirtiendo a escala de grises...")
    gray = _to_gray(bgr_corrected)
    save_debug_image("03_grayscale.png", gray)

    # 4. Denoising
    print("\n4. Eliminando ruido (NLM)...")
    gray_clean = _denoise(gray)
    save_debug_image("04_after_denoise.png", gray_clean)

    # 5. Detección de color
    print("\n5. Detectando color de tinta...")
    ink_color = _detect_ink_color(bgr_corrected)

    # 6. Binarización
    print("\n6. Binarizando...")
    binary = _binarize(bgr_corrected)
    save_debug_image("05_after_binarize.png", binary)
    print(f"   Píxeles blancos: {np.sum(binary > 0)}")

    # 7. Limpieza morfológica
    print("\n7. Limpiando morfología...")
    binary_clean = _clean_morphology(binary)
    save_debug_image("06_after_morphology.png", binary_clean)
    print(f"   Píxeles blancos después: {np.sum(binary_clean > 0)}")

    # 8. Eliminación de artefactos
    print("\n8. Eliminando artefactos...")
    binary_clean = _remove_artifacts(binary_clean)
    save_debug_image("07_after_artifact_removal.png", binary_clean)
    print(f"   Píxeles blancos después: {np.sum(binary_clean > 0)}")

    # 9. Detección de firma
    print("\n9. Detectando bounding box...")
    bbox = _find_signature_bbox(binary_clean)
    if bbox:
        x, y, w, h = bbox
        print(f"   Detectado en: x={x}, y={y}, w={w}, h={h}")

        # Visualizar bbox
        visual = binary_clean.copy()
        cv2.rectangle(visual, (x, y), (x + w, y + h), 128, 3)
        save_debug_image("08_bbox_detected.png", visual)

        # 10. Recorte con padding
        print("\n10. Recortando con padding...")
        x1, y1, x2, y2 = _add_padding(x, y, w, h, binary_clean.shape)
        binary_crop = binary_clean[y1:y2, x1:x2]
        save_debug_image("09_after_crop.png", binary_crop)
        print(f"   Recorte final: {binary_crop.shape}")

    else:
        print("   ERROR: No se detectó firma!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python debug_signature.py <archivo_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"ERROR: Archivo no encontrado: {pdf_path}")
        sys.exit(1)

    debug_signature(pdf_path)
    print(f"\nImagenes de debug guardadas en: {DEBUG_DIR}")
