"""
api/main.py — Wrapper FastAPI sobre el procesador de firmas.

Endpoints:
    GET  /                       Health check.
    POST /api/process            Sube archivo, devuelve PNG procesado (bytes).
    GET  /api/monday/teachers    Lista docentes con firma adjunta.
    POST /api/monday/process     Procesa firma de docente. Si upload=true,
                                 sube el PNG resultante a la columna Firma.

Usa los módulos existentes del proyecto (processor.py, monday_client.py,
docx_converter.py, pdf_converter.py) sin tocarlos.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# Agrega el directorio raíz al path para importar los módulos existentes.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from monday_client import (  # noqa: E402
    download_file,
    get_item_by_name,
    get_item_file_value,
    get_items_with_files,
    upload_file_to_column,
)
from processor import process_signature  # noqa: E402

# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------
app = FastAPI(title="Limpiador de Firmas — API", version="1.0.0")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ID de la columna "Firma" en Monday (la misma que usa monday_processor.py).
FIRMA_COLUMN_ID = os.getenv("MONDAY_FIRMA_COLUMN_ID", "archivo9")

SUPPORTED_EXTS = {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".doc"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class TeacherListItem(BaseModel):
    id: str
    name: str


class MondayProcessRequest(BaseModel):
    item_id: str
    upload_back: bool = False


class MondayProcessResponse(BaseModel):
    item_id: str
    teacher_name: str
    output_filename: str
    uploaded_to_monday: bool


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/")
def root() -> dict:
    return {"status": "ok", "service": "firmas-api"}


# ---------------------------------------------------------------------------
# POST /api/process — sube archivo, devuelve PNG procesado
# ---------------------------------------------------------------------------
@app.post("/api/process")
async def process_upload(file: UploadFile = File(...)) -> FileResponse:
    """
    Procesa un archivo de firma subido manualmente.
    Acepta PDF, JPG, PNG, DOCX, DOC. Devuelve el PNG limpio.
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Formato no soportado: '{ext}'. "
                f"Aceptados: {', '.join(sorted(SUPPORTED_EXTS))}"
            ),
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        in_path  = Path(tmpdir) / f"input{ext}"
        out_path = Path(tmpdir) / "output.png"

        contents = await file.read()
        in_path.write_bytes(contents)

        try:
            process_signature(str(in_path), str(out_path))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Error procesando: {type(exc).__name__}: {exc}",
            )

        # Copiar a un path persistente (FileResponse necesita que el archivo
        # exista cuando se envíe, pero el TemporaryDirectory se borra al salir).
        persistent = Path(tempfile.gettempdir()) / f"firma_{os.getpid()}_{file.filename}.png"
        persistent.write_bytes(out_path.read_bytes())

        return FileResponse(
            path=str(persistent),
            media_type="image/png",
            filename=Path(file.filename).stem + "_clean.png",
        )


# ---------------------------------------------------------------------------
# GET /api/monday/teachers — lista de docentes con firma adjunta
# ---------------------------------------------------------------------------
@app.get("/api/monday/teachers", response_model=list[TeacherListItem])
def list_monday_teachers() -> list[TeacherListItem]:
    """
    Devuelve los items del board que tienen un archivo en la columna Firma.
    """
    try:
        items = get_items_with_files(FIRMA_COLUMN_ID, limit=500)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return [TeacherListItem(id=item["id"], name=item["name"]) for item in items]


# ---------------------------------------------------------------------------
# POST /api/monday/process — procesa firma de Monday, opcionalmente la sube
# ---------------------------------------------------------------------------
@app.post("/api/monday/process")
def process_monday(req: MondayProcessRequest) -> JSONResponse:
    """
    Descarga la firma del item indicado, la procesa y (opcionalmente) sube
    el PNG resultante a la misma columna Firma.

    Devuelve metadatos. El PNG se obtiene aparte vía /api/monday/result/{item_id}
    si se necesita preview.
    """
    file_value = get_item_file_value(req.item_id, FIRMA_COLUMN_ID)
    if not file_value:
        raise HTTPException(
            status_code=404,
            detail=f"El item {req.item_id} no tiene firma adjunta en la columna {FIRMA_COLUMN_ID}",
        )

    try:
        files_data = json.loads(file_value)
        files = files_data.get("files", [])
    except (json.JSONDecodeError, KeyError) as exc:
        raise HTTPException(status_code=500, detail=f"Error parseando metadatos: {exc}")

    if not files:
        raise HTTPException(status_code=404, detail="No hay archivos en la columna")

    # Tomamos el primer archivo (los items suelen tener una sola firma).
    file_obj  = files[0]
    file_name = file_obj.get("name", f"firma_{req.item_id}")
    file_url  = file_obj.get("public_url") or file_obj.get("url")

    if not file_url:
        raise HTTPException(status_code=502, detail="Monday no devolvió URL del archivo")

    with tempfile.TemporaryDirectory() as tmpdir:
        in_path  = Path(tmpdir) / file_name
        out_path = Path(tmpdir) / f"{Path(file_name).stem}_clean.png"

        if not download_file(file_url, str(in_path)):
            raise HTTPException(status_code=502, detail="No se pudo descargar la firma de Monday")

        try:
            process_signature(str(in_path), str(out_path))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Error procesando: {type(exc).__name__}: {exc}",
            )

        # Guardar el PNG en cache para /api/monday/result/{item_id}.
        cached = _result_cache_path(req.item_id)
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(out_path.read_bytes())

        uploaded = False
        if req.upload_back:
            uploaded = upload_file_to_column(
                item_id=req.item_id,
                column_id=FIRMA_COLUMN_ID,
                file_path=str(out_path),
                file_name=f"{Path(file_name).stem}_clean.png",
            )
            if not uploaded:
                raise HTTPException(
                    status_code=502,
                    detail="Procesado OK, pero falló el upload a Monday",
                )

    # Obtener el nombre del docente para devolverlo.
    teacher_name = ""
    try:
        items = get_items_with_files(FIRMA_COLUMN_ID, limit=500)
        for it in items:
            if it["id"] == req.item_id:
                teacher_name = it["name"]
                break
    except RuntimeError:
        pass

    return JSONResponse(
        content=MondayProcessResponse(
            item_id=req.item_id,
            teacher_name=teacher_name,
            output_filename=f"{Path(file_name).stem}_clean.png",
            uploaded_to_monday=uploaded,
        ).dict()
    )


@app.get("/api/monday/result/{item_id}")
def get_monday_result(item_id: str) -> FileResponse:
    """Devuelve el PNG resultante de la última corrida de /api/monday/process para ese item."""
    cached = _result_cache_path(item_id)
    if not cached.exists():
        raise HTTPException(status_code=404, detail="No hay resultado en cache para ese item")
    return FileResponse(
        path=str(cached),
        media_type="image/png",
        filename=f"firma_{item_id}.png",
    )


def _result_cache_path(item_id: str) -> Path:
    safe_id = "".join(c for c in item_id if c.isalnum() or c in "-_")
    return Path(tempfile.gettempdir()) / "firmas_cache" / f"{safe_id}.png"
