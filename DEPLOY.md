# Guía de Deploy — Vercel + Railway

La solución se separa en dos servicios:

| Capa | Stack | Dónde corre | Por qué |
|---|---|---|---|
| **Frontend** | Next.js 14 (App Router) + Tailwind | Vercel | UI rápida, CDN global, deploy desde GitHub |
| **Backend** | FastAPI + OpenCV + LibreOffice | Railway (Docker) | OpenCV y LibreOffice no corren en Vercel; Railway corre Docker nativo |

```
[Browser] ──▶ [Next.js en Vercel] ──fetch──▶ [FastAPI en Railway] ──▶ [Monday.com API]
                  (web/)                          (api/ + Dockerfile)
```

---

## 1. Deploy del backend en Railway

### 1.1 Crear el proyecto

1. Entrá a [railway.app](https://railway.app) y conectá tu cuenta de GitHub.
2. **New Project → Deploy from GitHub repo → seleccioná `FrancoAdipa/script-limpiar-firma`.**
3. Railway detecta `Dockerfile` y `railway.json` automáticamente.

### 1.2 Variables de entorno (Railway → Settings → Variables)

| Variable | Valor | Para qué |
|---|---|---|
| `MONDAY_API_TOKEN` | Tu token de Monday | Auth con la API |
| `MONDAY_BOARD_ID` | ID del board con docentes | Apuntar al board correcto |
| `MONDAY_FIRMA_COLUMN_ID` | `archivo9` | ID de la columna de archivo "Firma" |
| `ALLOWED_ORIGINS` | URL del frontend en Vercel (ej `https://firmas.vercel.app`) | CORS |

### 1.3 Configurar dominio público

1. Railway → Settings → **Networking → Generate Domain**.
2. Te queda algo como `https://script-limpiar-firma-production.up.railway.app`.
3. Probá `https://<url>/` → debería devolver `{"status":"ok"}`.
4. Probá `https://<url>/api/monday/teachers` → debería devolver el array de docentes.

### 1.4 Costo

- Railway: free tier $5 USD/mes de crédito. Una API ociosa consume ~$2/mes. Procesar firmas suma poco (segundos de CPU).
- Si vas a procesar lotes grandes en serie, considerá Modal en su lugar (paga por segundo de cómputo, escala a 0).

---

## 2. Deploy del frontend en Vercel

### 2.1 Crear el proyecto

1. Entrá a [vercel.com](https://vercel.com) y conectá GitHub.
2. **Add New → Project → seleccioná `FrancoAdipa/script-limpiar-firma`.**
3. En **Framework Preset** Vercel detecta Next.js, pero necesita saber dónde está:
   - **Root Directory → `web`**.
4. Build settings: dejá los defaults (`next build`, output `.next`).

### 2.2 Variables de entorno (Vercel → Project Settings → Environment Variables)

| Variable | Valor | Aplica a |
|---|---|---|
| `API_BASE_URL` | URL pública del Railway (ej `https://script-limpiar-firma-production.up.railway.app`) | Production, Preview, Development |

⚠️ **No agregues el prefijo `NEXT_PUBLIC_`** — el código llama al backend desde route handlers del servidor (no del cliente), así que la URL queda oculta y no se filtra al navegador.

### 2.3 Deploy

Click **Deploy**. Termina en 1-2 minutos. La URL pública queda en tu dashboard.

### 2.4 Conectar dominio propio (opcional)

Vercel → Project → **Domains** → Add → seguí instrucciones para configurar DNS.

---

## 3. Loop final: CORS

Después del primer deploy de ambos lados:

1. Tomá la URL pública del Vercel (ej `https://firmas-adipa.vercel.app`).
2. En Railway → Variables → actualizá `ALLOWED_ORIGINS` con esa URL.
3. Restartá el servicio (Railway lo hace solo al cambiar env vars).

---

## 4. Desarrollo local

### Backend
```bash
cd "<repo>"
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r api/requirements.txt
cp .env.example .env  # completar con tu token y board id
uvicorn api.main:app --reload --port 8000
```

Para probar Word con firmas no embebidas:
```bash
brew install --cask libreoffice
```

### Frontend
```bash
cd web/
cp .env.example .env.local  # API_BASE_URL=http://localhost:8000
npm install
npm run dev  # abre http://localhost:3000
```

---

## 5. Troubleshooting

**"Faltan variables de entorno: MONDAY_API_TOKEN, MONDAY_BOARD_ID"**
→ Te falta setearlas en Railway (no en Vercel — el backend no las ve).

**El tab Monday tira error 500**
→ Revisá los logs de Railway. Lo más común: token expirado o board_id incorrecto.

**El PNG no se sube a Monday**
→ Verificá que `MONDAY_FIRMA_COLUMN_ID` apunte a una columna de **tipo File** en ese board.

**Vercel da error 504 (timeout)**
→ El procesamiento Python tardó >60s. Subí la imagen original a menor resolución, o pasate a plan Pro de Vercel (300s).

**LibreOffice no convierte un .doc**
→ El `.doc` está corrupto o tiene macros raras. Probá abrirlo en Word y guardarlo como `.docx`.
