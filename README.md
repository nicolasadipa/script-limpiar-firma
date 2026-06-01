# Script de Limpieza de Firmas Manuscritas

Sistema automático para procesar, limpiar y extraer firmas manuscritas de múltiples fuentes (PDF, JPG, PNG) con transparencia real y calidad profesional.

## Características

✅ **Soporte multi-formato**: PDF, JPG, PNG (con fallback para DOCX)  
✅ **Detección inteligente**: Identifica automáticamente tinta azul vs negra  
✅ **Pipeline robusto**: CLAHE + denoising + threshold adaptativo + morfología  
✅ **Transparencia real**: PNG RGBA con bordes anti-aliasing  
✅ **Escalado inteligente**: Hasta 1200px lado largo, preservando calidad  
✅ **Procesamiento masivo**: Batch processing con barra de progreso  
✅ **Logging dual**: Consola + archivo de log rotativo  

## Instalación

### Requisitos
- Python 3.8+
- OpenCV, PyMuPDF, NumPy, tqdm

### Pasos

```bash
# Clonar repositorio
git clone <repo-url>
cd script-limpiar-firma

# Crear entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt
```

## Uso

### Procesamiento simple

```bash
# Poner archivos en input/
mkdir input
# ... copiar PDF/JPG/PNG a input/ ...

# Procesar
python main.py

# Resultado en output/
```

### Procesamiento desde Monday.com

```bash
# Configurar .env
echo "MONDAY_API_KEY=tu_clave_aqui" > .env

# Procesar desde Monday
python monday_processor.py
```

### Test de un archivo

```bash
python test_single.py ruta/a/firma.pdf
```

## Configuración

Editar `config.py` para ajustar:
- **Denoising**: `DENOISE_H` (fuerza del suavizado)
- **Binarización**: `THRESH_BLOCK_SIZE`, `THRESH_C`
- **Morfología**: `MORPH_KERNEL_SIZE`, `MORPH_ITERATIONS`
- **Artifacts**: `MIN_COMPONENT_SIZE`
- **Salida**: `OUTPUT_LONG_SIDE_PX`, `PADDING_PX`

## Estructura

```
.
├── config.py                  # Configuración global
├── logger.py                  # Sistema de logging
├── processor.py               # Pipeline principal
├── pdf_converter.py           # Conversión PDF
├── main.py                    # Batch processor
├── test_single.py             # Test individual
├── monday_client.py           # Cliente Monday.com
├── monday_processor.py        # Procesador Monday
├── FORMATOS_SOPORTADOS.md     # Documentación
├── requirements.txt           # Dependencias
└── README.md                  # Este archivo
```

## Pipeline de Procesamiento

```
1. Remover footer (CamScanner, etc.)
2. Corrección de iluminación (CLAHE)
3. Conversión a escala de grises
4. Denoising (NLM)
5. Binarización (Threshold adaptativo)
6. Limpieza morfológica (Apertura)
7. Eliminación de artefactos
8. Detección de firma
9. Recorte + padding
10. Máscara suave (anti-aliasing)
11. Colorización a negro puro
12. Escalado
13. Unsharp mask (nitidez)
14. Exportación PNG RGBA
```

## Resultados

- **Entrada**: PDF/JPG/PNG ruidoso con firma
- **Salida**: PNG transparente (RGBA) 1200px, negro puro, bordes limpios

## Logs

Los logs se guardan en `logs/procesamiento.log` con rotación automática.

## Licencia

[Tu licencia aquí]

## Contacto

[Tu contacto aquí]
