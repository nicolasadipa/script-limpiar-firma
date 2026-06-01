# Imagen para correr el wrapper FastAPI con todas las dependencias nativas
# que necesita el pipeline de imagen (OpenCV) y la conversión Word→PDF
# (LibreOffice).
FROM python:3.11-slim

# Dependencias de sistema:
#   libreoffice → conversión .docx/.doc → PDF (fallback para firmas no embebidas)
#   libgl1, libglib2.0-0, libsm6, libxext6, libxrender1 → libs nativas de OpenCV
#   curl → healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias Python primero (mejor cache de capas Docker).
COPY requirements.txt /app/requirements.txt
COPY api/requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt -r /app/api/requirements.txt

# Copiar el resto del código.
COPY . /app

# Carpetas que el pipeline puede necesitar a runtime.
RUN mkdir -p /app/logs /app/input /app/output

# Railway/Fly inyectan PORT como env var; default 8000 para correr localmente.
ENV PORT=8000

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
