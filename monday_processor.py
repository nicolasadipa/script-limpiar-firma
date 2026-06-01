"""
monday_processor.py — Procesa firmas descargadas de Monday.com.

Conecta con Monday, busca un item específico, descarga la firma y la procesa
con el pipeline de limpieza.
"""

import os
import json
from pathlib import Path

from monday_client import (
    get_board_columns,
    get_item_by_name,
    get_item_file_value,
    download_file,
    get_asset_download_url,
)
from processor import process_signature
from logger import setup_logger

logger = setup_logger()


def process_docent_signature(docent_name: str) -> bool:
    """
    Descarga la firma de un docente desde Monday.com y la procesa.

    Args:
        docent_name: Nombre exacto del docente (ej: "TS. Rocío Troncoso").

    Returns:
        True si fue exitoso, False si falló.
    """
    logger.info(f"Buscando docente: '{docent_name}'")

    # ID conocido de la columna "Firma" en el board
    firma_col_id = "archivo9"
    logger.debug(f"Usando ID de columna 'Firma': {firma_col_id}")

    # Buscar el item del docente
    item = get_item_by_name(docent_name)

    if not item:
        logger.error(f"No se encontró el docente '{docent_name}'")
        return False

    item_id = item["id"]
    logger.info(f"Docente encontrado. Item ID: {item_id}")

    # Obtener el valor de la columna "Firma"
    file_value = get_item_file_value(item_id, firma_col_id)

    if not file_value:
        logger.error(f"El docente '{docent_name}' no tiene firma adjunta")
        return False

    # Parsear el JSON de archivos
    logger.debug(f"Raw file_value: {file_value}")

    try:
        files_data = json.loads(file_value)
        logger.debug(f"Parsed files_data: {files_data}")
        files = files_data.get("files", [])
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error(f"Error al parsear datos de archivos para '{docent_name}': {exc}")
        return False

    if not files:
        logger.error(f"No hay archivos en la columna 'Firma' para '{docent_name}'")
        return False

    logger.info(f"Se encontraron {len(files)} archivo(s)")

    # Descargar y procesar cada archivo
    for i, file_obj in enumerate(files):
        logger.debug(f"file_obj[{i}]: {file_obj}")

        file_name = file_obj.get("name", f"firma_{i}")

        # Obtener URL pública (S3 presignada, funciona sin autenticación)
        file_url = file_obj.get("public_url") or file_obj.get("url")

        if not file_url:
            logger.warning(f"Archivo sin URL en JSON: {file_name}")
            continue

        # Usar public_url si está disponible (S3 presignada)
        if file_obj.get("public_url"):
            logger.debug(f"Usando public_url (S3 presignada)")

        # Crear ruta temporal para descargar
        temp_dir = Path("temp_monday")
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / file_name

        logger.info(f"Descargando: {file_name}")

        if not download_file(file_url, str(temp_path)):
            logger.error(f"Error descargando {file_name}")
            continue

        # Procesar la firma descargada
        stem = Path(file_name).stem
        output_path = f"output/monday_{stem}.png"

        try:
            logger.info(f"Procesando: {file_name}")
            process_signature(str(temp_path), output_path)
            logger.info(f"Éxito: {file_name} → {output_path}")

            # Limpiar archivo temporal
            temp_path.unlink()
            return True

        except Exception as exc:
            logger.error(
                f"Error procesando {file_name}: {type(exc).__name__}: {exc}"
            )
            if temp_path.exists():
                temp_path.unlink()
            return False

    return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python monday_processor.py 'Nombre del Docente'")
        print("Ejemplo: python monday_processor.py 'TS. Rocío Troncoso'")
        sys.exit(1)

    docent = sys.argv[1]
    success = process_docent_signature(docent)
    sys.exit(0 if success else 1)
