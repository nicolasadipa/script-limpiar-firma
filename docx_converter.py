"""
docx_converter.py — Extrae imágenes de documentos Word (.docx y .doc).

Busca archivos incrustados (imágenes) en el documento y los convierte a arrays NumPy.
Soporta:
- .docx (formato Office Open XML) - via python-docx o extracción ZIP
- .doc (formato antiguo OLE) - intenta conversion o extracción directa
"""

import os
import cv2
import numpy as np
from io import BytesIO
import zipfile
import tempfile
import subprocess

try:
    from docx import Document
except ImportError:
    Document = None

from logger import setup_logger

logger = setup_logger()


def _extract_from_docx_zip(docx_path: str) -> list[np.ndarray]:
    """
    Extrae imágenes de un archivo .docx tratándolo como ZIP.
    Fallback para cuando python-docx falla.
    """
    images = []

    try:
        with zipfile.ZipFile(docx_path, 'r') as zip_ref:
            # Las imágenes en .docx están en word/media/
            for filename in zip_ref.namelist():
                if filename.startswith('word/media/'):
                    image_bytes = zip_ref.read(filename)
                    nparr = np.frombuffer(image_bytes, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    if img is not None:
                        images.append(img)
                        logger.debug(f"Imagen extraída de ZIP: {filename}")
    except Exception as exc:
        logger.debug(f"No se pudo extraer como ZIP: {exc}")

    return images


def _convert_doc_to_docx(doc_path: str) -> str:
    """
    Intenta convertir un archivo .doc antiguo a .docx usando libreoffice.

    Retorna la ruta al archivo .docx temporal, o levanta excepción si falla.
    """
    try:
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            docx_path = tmp.name

        # Intentar convertir con LibreOffice (si está disponible)
        subprocess.run(
            [
                'libreoffice', '--headless', '--convert-to', 'docx',
                '--outdir', os.path.dirname(docx_path),
                doc_path
            ],
            check=True,
            capture_output=True,
            timeout=30
        )

        # El archivo convertido se crea con el mismo nombre pero .docx
        converted_path = os.path.splitext(doc_path)[0] + '.docx'
        logger.debug(f"Documento convertido: {converted_path}")
        return converted_path

    except (FileNotFoundError, subprocess.CalledProcessError, Exception) as exc:
        logger.debug(f"No se pudo convertir .doc a .docx: {exc}")
        raise RuntimeError(
            f"No se puede procesar archivo .doc antiguo. "
            f"Requiere LibreOffice instalado o convertir a .docx manualmente."
        ) from exc


def extract_images_from_docx(docx_path: str) -> list[np.ndarray]:
    """
    Extrae todas las imágenes de un documento Word (.docx o .doc).

    Intenta múltiples métodos:
    1. python-docx (para .docx moderno)
    2. Extracción ZIP directa (para .docx fallido)
    3. Conversión con LibreOffice (para .doc antiguo)

    Args:
        docx_path: Ruta al archivo .docx o .doc

    Returns:
        Lista de arrays NumPy en formato BGR (OpenCV).
        Lista vacía si no hay imágenes.

    Raises:
        RuntimeError: Si el archivo no puede ser procesado.
    """
    images = []
    ext = os.path.splitext(docx_path)[1].lower()

    logger.debug(f"Procesando documento Word ({ext}): {docx_path}")

    # ---- MÉTODO 1: python-docx (preferido para .docx) ----
    if Document is not None:
        try:
            doc = Document(docx_path)

            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    image_part = rel.target_part
                    image_bytes = image_part.blob

                    nparr = np.frombuffer(image_bytes, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    if img is not None:
                        images.append(img)
                        logger.debug(
                            f"Imagen extraída (python-docx): "
                            f"{img.shape[1]}x{img.shape[0]} px"
                        )

            if images:
                return images

        except Exception as exc:
            logger.debug(f"python-docx falló: {exc}. Intentando alternativas...")

    # ---- MÉTODO 2: Extracción ZIP directa (para .docx dañados) ----
    if ext == '.docx':
        images = _extract_from_docx_zip(docx_path)
        if images:
            return images

    # ---- MÉTODO 3: Conversión .doc → .docx (para .doc antiguo) ----
    if ext == '.doc':
        try:
            logger.info("Documento .doc antiguo detectado. Intentando conversión...")
            docx_converted = _convert_doc_to_docx(docx_path)

            # Intentar nuevamente con el archivo convertido
            if Document is not None:
                doc = Document(docx_converted)
                for rel in doc.part.rels.values():
                    if "image" in rel.target_ref:
                        image_bytes = rel.target_part.blob
                        nparr = np.frombuffer(image_bytes, np.uint8)
                        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if img is not None:
                            images.append(img)

            # Limpiar archivo temporal
            try:
                os.remove(docx_converted)
            except:
                pass

            if images:
                return images

        except Exception as exc:
            logger.warning(f"Conversión .doc falló: {exc}")

    # ---- SIN IMÁGENES ----
    if not images:
        logger.warning(f"No se encontraron imágenes en '{docx_path}'")

    return images


def _try_convert_to_pdf_and_extract(docx_path: str) -> np.ndarray:
    """
    Intenta convertir documento a PDF y extraer primera página como imagen.
    Fallback cuando no hay imágenes incrustadas.
    """
    try:
        import subprocess
        import tempfile

        # Crear archivo temporal para PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            pdf_path = tmp.name

        # Intentar conversión con LibreOffice
        subprocess.run(
            [
                'libreoffice', '--headless', '--convert-to', 'pdf',
                '--outdir', os.path.dirname(pdf_path),
                docx_path
            ],
            check=True,
            capture_output=True,
            timeout=30
        )

        # Buscar el PDF generado
        base_name = os.path.splitext(os.path.basename(docx_path))[0]
        pdf_file = os.path.join(os.path.dirname(pdf_path), f"{base_name}.pdf")

        if os.path.exists(pdf_file):
            # Usar pdf_converter para procesar
            from pdf_converter import pdf_to_image
            img = pdf_to_image(pdf_file)

            # Limpiar archivos temporales
            try:
                os.remove(pdf_file)
                os.remove(pdf_path)
            except:
                pass

            return img

    except Exception as exc:
        logger.debug(f"Conversión a PDF falló: {exc}")

    return None


def _pick_signature_image(images: list[np.ndarray]) -> np.ndarray:
    """
    Elige la imagen que más probablemente sea la firma cuando el docx tiene
    varias imágenes embebidas (logo institucional + firma, etc.).

    Heurística: descartamos imágenes muy chicas (íconos) y entre las que
    quedan priorizamos área grande y aspecto apaisado (típico de firma).
    """
    if len(images) == 1:
        return images[0]

    MIN_SIDE_PX = 100
    candidates = [img for img in images if min(img.shape[:2]) >= MIN_SIDE_PX]
    if not candidates:
        candidates = images

    def score(img: np.ndarray) -> float:
        h, w = img.shape[:2]
        area = h * w
        aspect_bonus = 1.2 if w > h else 1.0
        return area * aspect_bonus

    best = max(candidates, key=score)
    h, w = best.shape[:2]
    logger.debug(
        f"Imagen seleccionada de {len(images)} candidatas: {w}x{h} px"
    )
    return best


def get_first_signature_from_docx(docx_path: str) -> np.ndarray:
    """
    Extrae la firma de un documento Word.

    Estrategia:
      1. Extrae todas las imágenes embebidas.
      2. Si hay varias, elige la más probable (la más grande y apaisada).
      3. Si no hay ninguna (firma dibujada como shape o InkML), convierte
         el documento a PDF con LibreOffice como fallback.

    Raises:
        ValueError: Si no se puede procesar el documento.
    """
    images = extract_images_from_docx(docx_path)

    if images:
        return _pick_signature_image(images)

    logger.info(
        f"No hay imágenes embebidas en '{docx_path}'. "
        "Intentando convertir a PDF con LibreOffice..."
    )

    pdf_image = _try_convert_to_pdf_and_extract(docx_path)

    if pdf_image is not None:
        logger.info("Documento convertido a PDF exitosamente")
        return pdf_image

    raise ValueError(
        f"No se pudieron extraer imágenes del documento '{docx_path}'. "
        "La firma no está embebida como imagen. Opciones: "
        "1) Pegá la firma como imagen en el Word, "
        "2) Convertí manualmente el .doc a .docx, "
        "3) Instalá LibreOffice (brew install --cask libreoffice en macOS) "
        "para conversión automática."
    )
