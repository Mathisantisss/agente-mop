# Despliegue Online — Agente MOP

## Opción A: Streamlit Community Cloud (gratis, más fácil)

### Paso 1 — Preparar el repositorio GitHub

1. Ve a [github.com](https://github.com) y crea un repositorio **privado** llamado `agente-mop`
2. En tu PC, abre CMD en `C:\Users\mathias.yanez\agente_mop` y ejecuta:

```bash
git init
git add app_publica.py agent.py local_agent.py cloud_agent.py config.py
git add requirements_cloud.txt .streamlit/config.toml .gitignore
git add Dockerfile railway.json
git commit -m "Agente MOP inicial"
git remote add origin https://github.com/TU_USUARIO/agente-mop.git
git push -u origin main
```

### Paso 2 — Migrar vectores a Pinecone (gratis)

1. Ve a [pinecone.io](https://www.pinecone.io) → crea cuenta gratis
2. Crea un API Key en el dashboard
3. Agrega al archivo `.env`:
   ```
   PINECONE_API_KEY=tu_clave_aqui
   ```
4. Ejecuta la migración (solo una vez):
   ```bash
   python migrate_to_pinecone.py
   ```
   Tarda ~5-10 minutos. Sube 31,952 vectores.

### Paso 3 — Desplegar en Streamlit Cloud

1. Ve a [share.streamlit.io](https://share.streamlit.io)
2. Conecta tu cuenta de GitHub
3. Selecciona el repositorio `agente-mop`
4. Archivo principal: `app_publica.py`
5. En **Advanced settings → Secrets**, agrega:
   ```toml
   GROQ_API_KEY = "gsk_tu_clave_groq"
   PINECONE_API_KEY = "tu_clave_pinecone"
   ```
6. Clic en **Deploy** → en 2-3 minutos tendrás una URL pública

✅ Tu app estará en: `https://agente-mop.streamlit.app`

---

## Opción B: Railway (más robusto, $5 crédito gratis/mes)

1. Ve a [railway.app](https://railway.app) → crea cuenta
2. New Project → Deploy from GitHub repo → selecciona `agente-mop`
3. En Variables, agrega `GROQ_API_KEY` y `PINECONE_API_KEY`
4. Railway detecta el `Dockerfile` automáticamente y despliega

---

## Opción C: Paquete de Escritorio

El paquete ya fue creado en tu Escritorio: `AgenteMOP_Instalador/`

Para distribuirlo:
1. Comprime la carpeta en un ZIP
2. Comparte el ZIP (Google Drive, WeTransfer, etc.)
3. El usuario descarga, extrae y ejecuta `SETUP.bat` (solo la primera vez)
4. Cada usuario necesita su propia clave Groq gratuita (se configura con `CONFIGURAR_CLAVE_GROQ.bat`)

### Tamaño del paquete de escritorio
- ZIP comprimido: ~80-100 MB
- Instalado: ~210 MB + dependencias Python (~500 MB, se instalan automáticamente)
