"""
test_single.py — Procesa un único archivo para pruebas y ajuste de parámetros.

Uso:
    python test_single.py "input/firma.jpg"

Útil para experimentar con diferentes valores en config.py sin procesar lotes enteros.
"""

import sys
import os
from pathlib import Path

from processor import process_signature
from logger import setup_logger

logger = setup_logger()


def main():
    if len(sys.argv) < 2:
        print("Uso: python test_single.py <ruta_archivo>")
        print("Ejemplo: python test_single.py input/firma.jpg")
        sys.exit(1)

    input_path = sys.argv[1]

    if not os.path.isfile(input_path):
        logger.error(f"Archivo no encontrado: {input_path}")
        sys.exit(1)

    # Generar ruta de salida
    stem = Path(input_path).stem
    output_path = f"output/test_{stem}.png"

    try:
        logger.info(f"Procesando: {input_path}")
        process_signature(input_path, output_path)
        logger.info(f"Éxito → {output_path}")
    except Exception as exc:
        logger.error(f"Error: {type(exc).__name__}: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
