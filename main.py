"""
main.py — Punto de entrada del sistema de procesamiento masivo de firmas.

Flujo:
  1. Escanea la carpeta 'input/' en busca de archivos soportados.
  2. Procesa cada archivo con el pipeline definido en processor.py.
  3. Guarda el resultado en 'output/' con el mismo nombre base y extensión .png.
  4. Muestra progreso con tqdm y registra cada resultado en el log.

Uso:
    python main.py
"""

import os
import time
from pathlib import Path

from tqdm import tqdm

import config
from logger import setup_logger
from processor import process_signature

logger = setup_logger()


def collect_input_files() -> list[Path]:
    """
    Recorre recursivamente la carpeta input/ y devuelve todos los archivos
    cuya extensión esté entre las soportadas (PDF, JPG, JPEG, PNG).
    """
    input_dir = Path(config.INPUT_DIR)
    if not input_dir.exists():
        logger.warning(f"La carpeta de entrada no existe: {input_dir}")
        input_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Carpeta creada: {input_dir}. Coloque archivos y vuelva a ejecutar.")
        return []

    files = [
        f for f in input_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in config.SUPPORTED_EXTENSIONS
    ]
    return sorted(files)


def build_output_path(input_file: Path) -> Path:
    """
    Calcula la ruta de salida manteniendo la estructura de subdirectorios
    relativa a input/ y cambiando la extensión a .png.

    Ejemplo:
        input/clientes/firma1.jpg → output/clientes/firma1.png
    """
    relative  = input_file.relative_to(config.INPUT_DIR)
    out_path  = Path(config.OUTPUT_DIR) / relative.with_suffix(".png")
    return out_path


def main() -> None:
    logger.info("=" * 60)
    logger.info("  PROCESADOR MASIVO DE FIRMAS DIGITALES")
    logger.info("=" * 60)

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    files = collect_input_files()

    if not files:
        logger.warning("No se encontraron archivos en la carpeta 'input/'. Proceso finalizado.")
        return

    logger.info(f"Archivos encontrados: {len(files)}")

    stats = {"ok": 0, "error": 0}

    # Barra de progreso principal
    progress_bar = tqdm(
        files,
        desc="Procesando firmas",
        unit="archivo",
        ncols=80,
        colour="cyan",
    )

    for input_file in progress_bar:
        filename   = input_file.name
        out_path   = build_output_path(input_file)

        progress_bar.set_postfix({"archivo": filename[:30]})
        start_time = time.perf_counter()

        try:
            process_signature(str(input_file), str(out_path))
            elapsed = time.perf_counter() - start_time

            logger.info(
                f"[OK]    {filename}  →  {out_path.name}  "
                f"({elapsed:.2f}s)"
            )
            stats["ok"] += 1

        except FileNotFoundError as exc:
            elapsed = time.perf_counter() - start_time
            logger.error(f"[ERROR] {filename} | Archivo no encontrado: {exc} ({elapsed:.2f}s)")
            stats["error"] += 1

        except ValueError as exc:
            elapsed = time.perf_counter() - start_time
            logger.warning(f"[WARN]  {filename} | Sin firma detectable: {exc} ({elapsed:.2f}s)")
            stats["error"] += 1

        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - start_time
            logger.error(
                f"[ERROR] {filename} | Error inesperado: {type(exc).__name__}: {exc} "
                f"({elapsed:.2f}s)"
            )
            stats["error"] += 1

    # Resumen final
    logger.info("-" * 60)
    logger.info(
        f"Procesamiento completado. "
        f"Éxitos: {stats['ok']}  |  Errores/Advertencias: {stats['error']}  |  "
        f"Total: {len(files)}"
    )
    logger.info(f"Archivos de salida en: {config.OUTPUT_DIR}")
    logger.info(f"Log guardado en:       {config.LOG_DIR}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
