# Formatos de Archivo Soportados

El sistema acepta múltiples formatos de entrada. Cada uno tiene requisitos específicos.

## ✅ Formatos Completamente Soportados

### 1. **PNG** (Recomendado)
- **Extensión:** `.png`
- **Requisitos:** Imagen con firma visible
- **Características:** Compresión sin pérdida, soporta transparencia
- **Cómo preparar:** Captura de pantalla o exportar desde cualquier editor

### 2. **JPG / JPEG**
- **Extensión:** `.jpg`, `.jpeg`
- **Requisitos:** Imagen con firma visible
- **Características:** Compresión con pérdida, archivo más pequeño
- **Cómo preparar:** Foto con celular, escaneo, captura de pantalla

### 3. **PDF**
- **Extensión:** `.pdf`
- **Requisitos:** PDF con firma en primera página
- **Características:** Texto e imágenes, múltiples páginas
- **Cómo preparar:** Escaneo directamente a PDF o exportar desde Word/otro software
- **Resolución:** Se procesa a 300 DPI automáticamente

### 4. **Word Moderno (.DOCX)**
- **Extensión:** `.docx`
- **Requisitos:** Firma PEGADA COMO IMAGEN dentro del documento
- **Características:** Documento editable con imagen incrustada
- **Cómo preparar:**
  1. Abre el archivo en Word
  2. Insert → Pictures → Elige imagen de firma
  3. Guarda como .docx
  4. Sube a Monday
- **Nota:** Si la firma está como TEXTO o FORMA, convierte primero a PDF

### 5. **Word Antiguo (.DOC)**
- **Extensión:** `.doc`
- **Requisitos:** Firma como IMAGEN + LibreOffice instalado
- **Características:** Formato antiguo de Microsoft Office
- **Cómo preparar:**
  1. Abre en Word
  2. Convierte a .docx (Archivo → Guardar Como → Word Document .docx)
  3. Sube el .docx a Monday
- **Nota:** Se recomienda actualizar a .docx

---

## ⚠️ Formatos con Requisitos Especiales

### Word sin imagen incrustada (Text/Shape)
**PROBLEMA:** Si la firma está como texto o forma (no como imagen):
```
❌ No funciona directamente
```

**SOLUCIONES:**
1. **Opción A - Convertir a PDF:**
   - Abre el Word → Guardar Como → PDF
   - Sube el PDF a Monday
   - ✅ Funciona

2. **Opción B - Pegar como imagen:**
   - Copia la firma (screenshot)
   - Abre el Word → Insert → Pictures → Pega imagen
   - Guarda como .docx
   - ✅ Funciona

3. **Opción C - Usar imagen directamente:**
   - Captura de pantalla (PNG/JPG)
   - Sube a Monday
   - ✅ Funciona inmediatamente

---

## 📊 Tabla de Compatibilidad

| Formato | Directo | Requisitos | Recomendación |
|---------|---------|-----------|----------------|
| PNG | ✅ Sí | Imagen con firma | ⭐ Mejor opción |
| JPG | ✅ Sí | Imagen con firma | ⭐ Muy buena |
| PDF | ✅ Sí | Firma en página 1 | ⭐ Excelente |
| DOCX (con imagen) | ✅ Sí | Firma incrustada | ✅ Funciona |
| DOC (con imagen) | ⚠️ Necesita LibreOffice | Firma incrustada + LibreOffice | ⚠️ No recomendado |
| DOCX (sin imagen) | ❌ No | Convertir a PDF | ❌ Cambiar formato |
| DOC (sin imagen) | ❌ No | Convertir a PDF | ❌ Cambiar formato |

---

## 🎯 Recomendación General

Para procesamiento masivo de 930+ elementos:

1. **Ideal:** PNG o JPG (imágenes directas)
   - Más rápido
   - Sin conversiones
   - Máxima compatibilidad

2. **Buena alternativa:** PDF
   - Si vienen de escaneos
   - Si están ya digitalizados

3. **Último recurso:** Word .docx
   - Solo si REQUIEREN usar Word
   - Asegurar que la firma esté como IMAGEN incrustada
   - Validar 1-2 muestras antes de procesar toda la colección

---

## 🔧 Verificar si Word tiene imagen incrustada

**En Word:**
1. Abre el archivo
2. Haz clic en la firma
3. ✅ Si puedes ver un "marco de imagen" alrededor = Es imagen
4. ❌ Si parece texto o líneas = No es imagen

**Si es texto/forma:**
- Convierte a PDF (Archivo → Guardar Como → PDF)
- O copia como imagen y pega de nuevo

---

## 📝 Ejemplos

### Ejemplo 1: Procesar JPG
```bash
# Simplemente pon la imagen en input/
# El sistema la procesa automáticamente
python main.py
```

### Ejemplo 2: Procesar PDF
```bash
# PDF de escaneo → procesamiento directo
python main.py
```

### Ejemplo 3: Procesar Word con imagen
```bash
# .docx con firma incrustada como imagen
# Se extrae y procesa automáticamente
python main.py
```

### Ejemplo 4: Convertir Word a PDF (si no tiene imagen)
```bash
# Si tienes Word sin imagen:
# LibreOffice → Archivo → Guardar Como → PDF
# O en línea: https://convertio.co/es/docx-pdf/
```
