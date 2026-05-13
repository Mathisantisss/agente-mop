# Agente MOP — Manual de Carreteras de Chile

Agente conversacional experto en los 9 volúmenes del Manual de Carreteras del MOP (Ministerio de Obras Públicas de Chile).

- Responde consultas técnicas con citas exactas (volumen y página)
- Listado determinístico de los 86 códigos de señales del manual
- Genera reportes en **Excel**, **Word** y **PDF**
- Powered by **Claude Opus 4.7** con prompt caching y adaptive thinking

---

## 🚀 Deployment en Streamlit Cloud (uso empresarial)

### Pre-requisitos
- Cuenta en [GitHub](https://github.com)
- Cuenta en [Streamlit Cloud](https://share.streamlit.io) (gratis, login con GitHub)
- Clave API de Anthropic ([console.anthropic.com](https://console.anthropic.com/settings/keys))
- **Git LFS instalado** ([git-lfs.com](https://git-lfs.com)) — necesario para los vectores

### Paso 1 — Preparar el repositorio local

```bash
# 1. Instalar Git LFS (una sola vez)
git lfs install

# 2. Inicializar el repo
git init
git add .
git commit -m "Initial commit: Agente MOP listo para deployment"
```

### Paso 2 — Subir a GitHub

1. Crea un repo **privado** en GitHub: `agente-mop`
2. Sube el código:

```bash
git remote add origin https://github.com/TU-USUARIO/agente-mop.git
git branch -M main
git push -u origin main
```

> Si tienes archivos grandes, Git LFS los maneja automáticamente al hacer push.

### Paso 3 — Deploy en Streamlit Cloud

1. Ve a [share.streamlit.io](https://share.streamlit.io) → "New app"
2. Conecta tu repo `agente-mop`
3. Branch: `main`, Main file path: `app_anthropic.py`
4. Click "**Advanced settings**" → **Secrets**, pega:

```toml
ANTHROPIC_API_KEY = "sk-ant-api03-..."
APP_PASSWORD = "elige-una-contraseña-larga-y-segura"
```

5. Click "Deploy"
6. En ~3 minutos tu URL queda lista: `https://[nombre].streamlit.app`

### Paso 4 — Compartir con tu empresa

Comparte 2 cosas:
1. La URL: `https://[nombre].streamlit.app`
2. La contraseña que configuraste en `APP_PASSWORD`

---

## 💻 Uso local (desarrollo)

### Requisitos
- Python 3.10+
- Clave API de Anthropic

### Instalación

```bash
pip install -r requirements.txt
```

### Configuración

Crea un archivo `.env` en la raíz con:

```
ANTHROPIC_API_KEY=sk-ant-api03-...
```

O alternativamente, crea `.streamlit/secrets.toml`:

```toml
ANTHROPIC_API_KEY = "sk-ant-api03-..."
APP_PASSWORD = "tu-password-local"
```

### Ejecutar

```bash
streamlit run app_anthropic.py
```

Abre [http://localhost:8501](http://localhost:8501)

---

## 📁 Estructura del proyecto

```
agente_mop/
├── app_anthropic.py        ← App principal (Streamlit + Claude)
├── agent.py                ← Herramientas (tool use): RAG, Excel, Word, PDF
├── signs_db.py             ← Base estructurada de señales (regex)
├── local_agent.py          ← Lógica de búsqueda RAG mejorada
├── config.py               ← Rutas y configuración
├── ingest.py               ← Vectorización de PDFs (uso inicial)
├── chroma_db/              ← Base vectorial (31.952 fragmentos, ~210 MB)
├── reportes/               ← Excel/Word/PDF generados (runtime)
├── requirements.txt        ← Dependencias Python
├── .streamlit/
│   ├── config.toml         ← Tema visual
│   └── secrets.toml        ← Claves (NO va al repo)
├── .gitignore
├── .gitattributes          ← Configuración de Git LFS
└── README.md
```

---

## 🔒 Seguridad

- ✅ La pantalla de login bloquea acceso sin contraseña
- ✅ La clave API vive solo en "secrets" del servidor (no en código)
- ✅ HTTPS automático en Streamlit Cloud
- ✅ Comparación de contraseña con `hmac.compare_digest` (a prueba de timing attacks)

Para cambiar la contraseña: edita `APP_PASSWORD` en Streamlit Cloud Settings → Secrets.

---

## 💰 Costos estimados

- **Streamlit Cloud:** gratis
- **GitHub:** gratis (repo privado)
- **Git LFS:** gratis hasta 1 GB de storage
- **Anthropic API:** pago por uso
  - ~$0.04 USD por consulta típica
  - Con prompt caching, consultas siguientes en la misma sesión: ~$0.005 USD

**Estimación empresa de 20 personas × 10 consultas/día:**
- Sin caché: ~$80 USD/mes
- Con caché (más realista): ~$30-50 USD/mes

---

## 🔧 Mantenimiento

### Actualizar el código
```bash
git add .
git commit -m "Descripción del cambio"
git push
```
Streamlit Cloud detecta el push y redespliega automáticamente.

### Cambiar el modelo
En `app_anthropic.py`, edita `MODELO_CLAUDE`:
- `claude-opus-4-7` — máxima calidad (default)
- `claude-sonnet-4-6` — ~5× más barato, sigue siendo excelente
- `claude-haiku-4-5` — más rápido y económico

### Ver logs
Streamlit Cloud → Tu app → "Manage app" → "Logs"

---

## 📞 Soporte

Ministerio de Obras Públicas — Chile
