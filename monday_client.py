"""
monday_client.py — Cliente para interactuar con Monday.com API.

Proporciona funciones para obtener items, columnas y descargar archivos adjuntos
desde un board específico de Monday.com usando GraphQL.
"""

import os
import json
import requests
from typing import Any, Optional
from dotenv import load_dotenv

from logger import setup_logger

logger = setup_logger()

load_dotenv()

MONDAY_API_URL = "https://api.monday.com/v2"
MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN")
MONDAY_BOARD_ID = os.getenv("MONDAY_BOARD_ID")


def _make_request(query: str, variables: Optional[dict] = None) -> dict:
    """
    Ejecuta una consulta GraphQL contra Monday.com API.

    Args:
        query: Consulta GraphQL.
        variables: Variables para la consulta (opcional).

    Returns:
        Respuesta JSON de Monday.com.

    Raises:
        RuntimeError: Si la API retorna un error.
    """
    if not MONDAY_API_TOKEN:
        raise RuntimeError(
            "MONDAY_API_TOKEN no está configurado en .env. "
            "Añade tu token de Monday.com."
        )

    headers = {
        "Authorization": MONDAY_API_TOKEN,
        "Content-Type": "application/json",
    }

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        response = requests.post(
            MONDAY_API_URL, json=payload, headers=headers, timeout=30
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Error en solicitud a Monday.com: {exc}") from exc

    data = response.json()

    if "errors" in data:
        error_msg = data["errors"][0].get("message", "Error desconocido")
        raise RuntimeError(f"Error en consulta GraphQL: {error_msg}")

    return data.get("data", {})


def get_board_columns() -> dict[str, str]:
    """
    Obtiene todas las columnas del board (incluyendo ocultas).

    Returns:
        Dict con {nombre_columna: id_columna}
    """
    query = """
    query {
        boards(ids: [%s]) {
            columns {
                id
                title
                hidden
            }
        }
    }
    """ % MONDAY_BOARD_ID

    data = _make_request(query)
    board = data["boards"][0]

    columns_map = {}
    for col in board["columns"]:
        columns_map[col["title"]] = col["id"]
        status = "(oculta)" if col.get("hidden") else ""
        logger.debug(f"Columna: {col['title']:30} ID: {col['id']:15} {status}")

    return columns_map


def get_items_with_files(
    file_column_id: str, limit: int = 50, offset: int = 0
) -> list[dict]:
    """
    Obtiene items del board que tengan archivos adjuntos en una columna específica.

    Args:
        file_column_id: ID de la columna de archivos (ej: la columna "Firma").
        limit: Número máximo de items a obtener.
        offset: Desplazamiento para paginación.

    Returns:
        Lista de items con sus datos.
    """
    query = """
    query {
        boards(ids: [%s]) {
            items_page(limit: %d, offset: %d) {
                items {
                    id
                    name
                    column_values(ids: ["%s"]) {
                        id
                        value
                    }
                }
            }
        }
    }
    """ % (MONDAY_BOARD_ID, limit, offset, file_column_id)

    data = _make_request(query)
    board = data["boards"][0]

    items_with_files = []
    for item in board["items_page"]["items"]:
        col_val = item["column_values"][0]
        if col_val.get("value"):
            items_with_files.append(item)

    return items_with_files


def get_item_by_name(name: str) -> Optional[dict]:
    """
    Busca un item por nombre exacto.

    Args:
        name: Nombre del item (ej: "TS. Rocío Troncoso").

    Returns:
        Dict del item o None si no se encuentra.
    """
    query = """
    query {
        boards(ids: [%s]) {
            items_page(limit: 500) {
                items {
                    id
                    name
                }
            }
        }
    }
    """ % MONDAY_BOARD_ID

    data = _make_request(query)
    board = data["boards"][0]

    for item in board["items_page"]["items"]:
        if item["name"].strip().lower() == name.strip().lower():
            return item

    return None


def get_item_file_value(item_id: str, file_column_id: str) -> Optional[str]:
    """
    Obtiene los archivos de una columna específica con sus public_url (URLs S3 presignadas).

    Args:
        item_id: ID del item.
        file_column_id: ID de la columna de archivo (ej: "archivo9" para Firma).

    Returns:
        String JSON con los archivos incluyendo public_url o None si no hay.
    """
    # Primero obtener el valor de la columna (JSON con metadatos)
    query = """
    query {
        items(ids: ["%s"]) {
            id
            name
            column_values(ids: ["%s"]) {
                id
                value
            }
        }
    }
    """ % (item_id, file_column_id)

    try:
        data = _make_request(query)
        items = data.get("items", [])

        if not items:
            logger.warning(f"No se encontró el item {item_id}")
            return None

        col_values = items[0].get("column_values", [])
        if not col_values or not col_values[0].get("value"):
            logger.warning(f"No hay archivos en la columna {file_column_id}")
            return None

        # Parsear el JSON de metadatos
        value_json = col_values[0]["value"]
        files_meta = json.loads(value_json)
        asset_ids = [f["assetId"] for f in files_meta.get("files", [])]

        if not asset_ids:
            return None

        # Ahora obtener los assets específicos con public_url
        query2 = """
        query {
            items(ids: ["%s"]) {
                assets {
                    id
                    name
                    url
                    public_url
                }
            }
        }
        """ % item_id

        data2 = _make_request(query2)
        assets = data2.get("items", [{}])[0].get("assets", [])

        # Filtrar solo los assets que están en esta columna
        filtered_assets = [
            a for a in assets
            if int(a.get("id", 0)) in asset_ids
        ]

        if filtered_assets:
            logger.info(
                f"Se obtuvieron {len(filtered_assets)} archivo(s) "
                f"de la columna {file_column_id}"
            )
            return json.dumps({"files": filtered_assets})
        else:
            logger.warning(f"No hay assets para la columna {file_column_id}")
            return None

    except (RuntimeError, json.JSONDecodeError, KeyError) as exc:
        logger.error(f"Error obteniendo archivos de columna: {exc}")
        return None


def _get_item_file_value_fallback(item_id: str, file_column_id: str) -> Optional[str]:
    """Método alternativo: obtiene files con todas sus propiedades incluyendo URL."""
    query = """
    query {
        items(ids: ["%s"]) {
            files(ids: ["%s"]) {
                id
                name
                size
                createdAt
                createdBy {
                    id
                    name
                }
                assetId
                fileType
                isImage
                url
            }
        }
    }
    """ % (item_id, file_column_id)

    try:
        data = _make_request(query)
        items = data.get("items", [])

        if not items:
            logger.warning(f"No se encontraron items con files")
            # Fallback final: usar column_values
            return _get_column_value_raw(item_id, file_column_id)

        files = items[0].get("files", [])
        if files:
            logger.debug(f"Se obtuvieron {len(files)} archivo(s) con URLs")
            return json.dumps({"files": files})
        else:
            logger.warning(f"No hay files en {file_column_id}")
            return _get_column_value_raw(item_id, file_column_id)

    except RuntimeError as exc:
        logger.debug(f"Query de files falló: {exc}. Intentando column_values...")
        return _get_column_value_raw(item_id, file_column_id)


def _get_column_value_raw(item_id: str, file_column_id: str) -> Optional[str]:
    """
    Obtiene el valor de column_values que contiene JSON con files y URL en campo 'text'.
    Monday.com devuelve la URL accesible en el campo 'text'.
    """
    query = """
    query {
        items(ids: ["%s"]) {
            column_values(ids: ["%s"]) {
                id
                value
                text
            }
        }
    }
    """ % (item_id, file_column_id)

    try:
        data = _make_request(query)
        items = data.get("items", [])

        if items and items[0].get("column_values"):
            col_val = items[0]["column_values"][0]

            # El campo 'value' contiene JSON con metadatos
            value_json = col_val.get("value")
            # El campo 'text' contiene la URL de descarga
            file_url = col_val.get("text")

            if value_json and file_url:
                # Combinar: JSON con metadatos + URL real
                try:
                    files_data = json.loads(value_json)
                    # Agregar la URL al primer archivo
                    if files_data.get("files"):
                        files_data["files"][0]["url"] = file_url
                    return json.dumps(files_data)
                except json.JSONDecodeError:
                    pass

            if value_json:
                return value_json

    except RuntimeError as exc:
        logger.warning(f"Error en query column_values: {exc}")

    return None


def download_file(file_url: str, output_path: str) -> bool:
    """
    Descarga un archivo desde una URL (generalmente S3 presignada de Monday.com).

    Args:
        file_url: URL del archivo.
        output_path: Ruta donde guardar el archivo.

    Returns:
        True si fue exitoso, False si falló.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        response = requests.get(
            file_url,
            timeout=30,
            stream=True,
            allow_redirects=True,
        )
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"Archivo descargado: {output_path}")
        return True

    except requests.exceptions.RequestException as exc:
        logger.error(f"Error descargando archivo: {exc}")
        return False


def get_asset_download_url(asset_id: str, file_name: str) -> Optional[str]:
    """
    Construye la URL de descarga de un asset usando el CDN de Monday.

    Args:
        asset_id: ID del asset.
        file_name: Nombre del archivo.

    Returns:
        URL de descarga o None.
    """
    # Monday.com CDN URL pattern
    urls_to_try = [
        f"https://cdn.monday.com/asset?assetId={asset_id}&download",
        f"https://cdn.monday.com/asset?assetId={asset_id}",
        f"https://api.monday.com/v1/assets/{asset_id}/download",
    ]

    for url in urls_to_try:
        try:
            headers = {
                "Authorization": MONDAY_API_TOKEN,
            }
            response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)

            # Si el HEAD funciona (200 o 302), usar el URL
            if response.status_code in [200, 302]:
                logger.debug(f"URL de descarga válida: {url}")
                return url

        except requests.exceptions.RequestException:
            continue

    logger.warning(f"No se pudo construir URL válida para asset {asset_id}")
    return None
