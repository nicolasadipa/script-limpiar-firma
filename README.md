# Script de Limpieza de Firmas Manuscritas

Sistema automático para procesar, limpiar y extraer firmas manuscritas de múltiples fuentes (PDF, JPG, PNG, DOCX, DOC) con transparencia real y calidad profesional.

## Características

- **Soporte multi-formato**: PDF, JPG, PNG, DOCX, DOC (con LibreOffice opcional para Word con firmas dibujadas).
- **Detección automática de color de tinta**: distingue azul vs negra y aplica el canal con mejor contraste a cada caso.
- **Pipeline basado en mapa de tinta** (no en escala de grises): para tinta azul usa saturación HSV; para negra usa el canal R invertido. Esto separa la firma del papel incluso cuando el fondo es grisáceo y la luminancia es parecida a la tinta.
- **Binarización Otsu adaptativa**: corte automático con margen para capturar trazos finos.
- **Limpieza morfológica + filtro por componentes conectados** para eliminar puntos aislados y ruido residual.
- **Transparencia real**: PNG RGBA con bordes anti-aliasing.
- **Escalado inteligente** hasta 1200px en el lado largo.
- **Procesamiento masivo** con barra de progreso y logging dual (consola + archivo).
- **Integración con Monday.com**: descarga firmas desde un board por nombre de docente.

## Instalación

### Requisitos
- Python 3.8+
- OpenCV, PyMuPDF, NumPy, tqdm, python-docx, python-dotenv, requests
- **(Opcional)** LibreOffice — sólo necesario si tus Words tienen firmas dibujadas como shape/InkML en lugar de imagen embebida, o si trabajás con `.doc` antiguos.

### Pasos

```bash
git clone https://github.com/FrancoAdipa/script-limpiar-firma.git
cd script-limpiar-firma

python -m venv venv
source venv/bin/activate   # macOS / Linux
# venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

### LibreOffice (opcional, recomendado)

Para que el script soporte Words con firmas no embebidas como imagen:

```bash
# macOS
brew install --cask libreoffice

# Ubuntu / Debian
sudo apt install libreoffice

# Windows
# Descargar desde https://www.libreoffice.org/download/
```

El script lo detecta automáticamente. Si no está instalado, los Words con firma embebida como imagen siguen funcionando; sólo los `.doc` antiguos o Words con firma dibujada como shape fallarán.

## Uso

### Procesamiento por lote (carpeta `input/`)

```bash
mkdir input
# Copiá los archivos a input/ (PDF, JPG, PNG, DOCX, DOC)
python main.py
# Resultados en output/
```

### Procesamiento desde Monday.com

1. Copiá `.env.example` a `.env`:
   ```bash
   cp .env.example .env
   ```
2. Editá `.env` con tu token y board ID.
3. Procesá un docente específico:
   ```bash
   python monday_processor.py "TS. Rocío Troncoso"
   ```

### Test de un archivo individual

```bash
python test_single.py ruta/a/firma.pdf
```

## Configuración

Editá `config.py` para ajustar el pipeline. Parámetros clave:

| Parámetro | Default | Sirve para |
|---|---|---|
| `BLUE_INK_RATIO` | 0.30 | Umbral azul-vs-negra. Subilo si firmas casi negras se clasifican como azules. |
| `BLUE_INK_MIN_SAT` | 30 | Saturación mínima para considerar azul. Subir si confunde sombras azuladas con tinta. |
| `THRESH_C` | 15 | Cuánto bajar del corte Otsu para capturar trazos finos. Más alto = más sensible (puede tomar ruido). |
| `MIN_INK_THRESHOLD` | 25 | Piso absoluto de binarización. Subir si el fondo se cuela. |
| `DENOISE_H` | 16 | Fuerza del NLM. Más alto = más suave pero pierde detalle. |
| `MIN_COMPONENT_SIZE` | 95 | Área mínima de componente. Subir para eliminar más motas; bajar si pierde puntos de la firma. |
| `PADDING_PX` | 30 | Margen alrededor del crop final. |
| `OUTPUT_LONG_SIDE_PX` | 1200 | Tamaño objetivo del lado largo en el PNG de salida. |

## Pipeline de procesamiento

```
1.  Carga del archivo (rasterización si es PDF/DOCX)
2.  Detección y recorte de footer de escáner (línea divisoria horizontal)
3.  Corrección de iluminación (CLAHE sobre canal L de LAB)
4.  Detección automática de color de tinta (azul vs negra)
5.  Extracción del mapa de tinta:
       - Azul  → saturación HSV
       - Negra → canal R invertido
6.  Denoising NLM sobre el mapa de tinta
7.  Binarización Otsu (firma=blanco, fondo=negro)
8.  Limpieza morfológica (apertura)
9.  Filtrado de componentes conectados pequeños / líneas delgadas
10. Detección del bounding-box de la firma (con filtro por centroide)
11. Crop + padding
12. Máscara alfa con bordes anti-aliasing (preserva huecos internos)
13. Colorización a negro puro
14. Escalado a 1200px lado largo (Lanczos)
15. Unsharp mask
16. Exportación PNG RGBA
```

## Por qué mapa de tinta y no escala de grises

Cuando el papel tiene un tono parecido a la tinta (escaneos amarillentos, firmas azules sobre fondos grisáceos), la escala de grises colapsa firma y fondo a valores casi iguales, y cualquier threshold los corta a la par. El mapa de tinta usa el canal de **color** que mejor separa una tinta específica del fondo:

- **Azul:** la tinta azul tiene saturación alta (S~150-255). Cualquier fondo gris/blanco tiene saturación casi cero. Un threshold sobre el canal S separa la firma del fondo casi sin ambigüedad.
- **Negra:** la tinta negra tiene rojo (R) muy bajo. Fondos claros tienen R alto. El canal `255 - R` deja la firma en valores altos y el fondo en valores bajos.

Otsu corta automáticamente en el valle de esta distribución bimodal, y `THRESH_C` da margen para que los trazos finos no se pierdan en el borde del corte.

## Estructura del proyecto

```
.
├── config.py              # Parámetros del pipeline (todo se ajusta acá)
├── logger.py              # Logging dual (consola + archivo rotativo)
├── processor.py           # Pipeline de limpieza (entry point: process_signature)
├── pdf_converter.py       # Rasterización de PDF con PyMuPDF
├── docx_converter.py      # Extracción de imágenes de Word (.docx/.doc)
├── main.py                # Batch sobre la carpeta input/
├── test_single.py         # Test individual
├── monday_client.py       # Cliente GraphQL de Monday.com
├── monday_processor.py    # Descarga firma de Monday y procesa
├── requirements.txt       # Dependencias Python
├── .env.example           # Plantilla de variables de entorno
└── README.md
```

## Logs

Los logs se guardan en `logs/procesamiento.log` con rotación automática.
