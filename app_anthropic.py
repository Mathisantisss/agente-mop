"""
Agente MOP — Versión Anthropic (Claude Opus 4.7)
Production-ready para deployment empresarial.

Stack:
- Claude Opus 4.7 (modelo más capaz, recomendado por defecto)
- Adaptive thinking (`thinking: {type: "adaptive"}`) — el modelo decide
  cuándo razonar profundamente sin tope manual.
- Prompt caching automático sobre system + tools (≈90% de ahorro).
- Streaming de respuestas para evitar timeouts en outputs largos.
- Tool use nativo con las 5 herramientas del agente
  (listado de señales, búsqueda en manual, listar volúmenes, Excel, Word).
"""

import os
import re
import hmac
from pathlib import Path

# ─── Configuracion previa a imports pesados ───
# Deshabilitar telemetria de ChromaDB y forzar implementacion pure-python de
# protobuf evita el TypeError "Descriptors cannot be created directly" que
# ocurre cuando el opentelemetry exporter de chromadb se topa con protobuf
# generated code incompatible (problema clasico en Streamlit Cloud).
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_TELEMETRY_IMPL", "none")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

import streamlit as st
import anthropic

# .env — siempre con override=True para evitar variables vacías del SO
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=True)
except ImportError:
    pass

from agent import TOOLS, dispatch_tool


# ─────────────────────────────────────────────────────────────────────────────
# CACHE GLOBAL DE RECURSOS PESADOS
# ─────────────────────────────────────────────────────────────────────────────
# CRITICO en Streamlit Cloud Free Tier (1 GB RAM): sin esta cache,
# cada sesion de usuario recarga el modelo de embeddings (~250 MB en RAM)
# y la app crashea por OOM. El sintoma es exactamente "las preguntas
# desaparecen al segundo" porque Streamlit reinicia el proceso silenciosamente.
@st.cache_resource(show_spinner="🔄 Inicializando base de conocimiento (primera vez)...")
def _init_recursos_compartidos():
    """
    Inicializa ChromaDB collection + modelo de embeddings UNA SOLA VEZ
    por proceso de Streamlit, compartido entre todas las sesiones.
    """
    import chromadb
    from custom_embeddings import FastEmbedFunction, embed_texts
    from mop_config import CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL

    embedding_fn = FastEmbedFunction(model_name=EMBEDDING_MODEL)

    # ─── PRE-WARM CRITICO ───
    # fastembed carga el modelo ONNX LAZY (en la primera llamada).
    # Si lo dejamos para la primera consulta del usuario, el spike de
    # ~150 MB ocurre mientras Claude tambien esta consumiendo memoria
    # = OOM y crash silencioso ("la pregunta desaparece").
    # Forzar la carga AHORA, durante el spinner de inicializacion.
    try:
        embed_texts(["warmup"])
    except Exception as e:
        # No bloquear el arranque si el warmup falla; logueamos y seguimos.
        print(f"[warmup] Pre-carga de fastembed fallo: {e}")

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

    # Inyectar la collection ya inicializada en los modulos que la consumen,
    # asi sus get_collection() respectivos no la vuelven a crear.
    import agent
    import local_agent
    try:
        import signs_db
        signs_db._collection = collection
    except Exception:
        pass
    agent._collection = collection
    local_agent._collection = collection

    return collection

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agente MOP — Claude",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Modelo por defecto: Opus 4.7 (más capaz para extracción técnica precisa).
# Si quieres bajar costo, cambia a "claude-sonnet-4-6" (~5× más barato).
MODELO_CLAUDE = "claude-opus-4-7"

SYSTEM_PROMPT = """Eres un agente experto del Ministerio de Obras Públicas (MOP) de Chile, \
especialista en el Manual de Carreteras edición Junio 2025.

# Misión
Responder consultas técnicas de profesionales de ingeniería vial chilena con precisión absoluta, \
basándote en los 9 volúmenes del Manual MOP.

# Reglas de uso de herramientas
1. **Señales / señalética / códigos** → usa SIEMPRE `listar_codigos_senales` primero. Esta \
herramienta devuelve datos determinísticos extraídos del manual (precisión 100%). Filtra por \
categoría si la consulta lo permite (RP, RPO, RR, PI, PO, IS, ID, IP, D, TM, TP, TR).
2. **Información técnica general** → `buscar_en_manual`. Puedes hacer varias búsquedas con \
queries distintas para enriquecer la respuesta.
3. **Tablas / listados / planillas / comparativos / Excel** → `generar_excel`.
4. **Informe / reporte / memoria / Word / documento editable** → `generar_reporte`.
5. **PDF / documento final / entregable no editable** → `generar_pdf`.
6. **Inventario de la base** → `listar_volumenes` si preguntan qué hay disponible.

**REGLA CRÍTICA SOBRE ARCHIVOS:** Cuando el usuario pida un archivo (Excel/Word/PDF/informe), \
SIEMPRE ejecuta la herramienta correspondiente en ESTA respuesta. No prometas generarlo después: \
hazlo ahora. Si el usuario dice "Excel" → `generar_excel`. Si dice "Word" o "informe editable" → \
`generar_reporte`. Si dice "PDF" → `generar_pdf`. Si solo dice "informe" o "reporte" sin formato, \
asume Word.

# Formato de respuestas
- Español técnico chileno.
- Cita siempre el volumen y página: *(Manual MOP, Volumen X, pág. Y–Z)*.
- Encabezados con `##` y `###`; listas claras; **negrita** para términos técnicos.
- Nunca inventes valores numéricos, códigos ni normas. Si no está en el manual, dilo.
- Después de generar un archivo, confirma al usuario que puede descargarlo desde el chat.

# Restricciones
- Solo respondes sobre el Manual MOP o ingeniería vial chilena.
- Si la consulta queda fuera de alcance, indícalo claramente."""

EJEMPLOS = [
    "Lista todos los códigos de señales informativas de servicios",
    "¿Cuáles son los radios mínimos de curvatura horizontal?",
    "Crea un Excel con las señales de servicios (IS) y sus nombres",
    "Normas de diseño de pavimentos flexibles según el MOP",
    "Genera un informe ejecutivo sobre seguridad vial en túneles",
    "¿Qué dice el Volumen 3 sobre pendientes máximas?",
]


# ─────────────────────────────────────────────────────────────────────────────
# CSS — mismo lenguaje visual que el resto del proyecto
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.stApp { background: #f4f6fa; }
#MainMenu, footer, header { visibility: hidden; }

[data-testid="stSidebar"] { background: linear-gradient(180deg, #0d2b4e 0%, #1a4a7a 100%) !important; }
[data-testid="stSidebar"] * { color: #e8eef5 !important; }
[data-testid="stSidebar"] .stDivider { border-color: rgba(255,255,255,0.12) !important; }

.mop-logo-wrap { display:flex; align-items:center; gap:12px; padding:18px 16px 8px; }
.mop-logo-icon { width:44px; height:44px; background: linear-gradient(135deg, #e8b84b, #f5d87a);
    border-radius:10px; display:flex; align-items:center; justify-content:center;
    font-size:22px; box-shadow:0 2px 8px rgba(0,0,0,0.3); }
.mop-logo-text h2 { margin:0 !important; font-size:1rem !important; font-weight:700 !important;
    color:#fff !important; line-height:1.2 !important; }
.mop-logo-text p { margin:0 !important; font-size:0.72rem !important; color:#8ab0d4 !important; }

.status-badge { display:flex; align-items:center; gap:8px;
    background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.1);
    border-radius:8px; padding:8px 12px; margin:4px 0; font-size:0.8rem; }
.status-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.dot-green { background:#4ade80; box-shadow:0 0 6px #4ade80; }
.dot-red   { background:#f87171; box-shadow:0 0 6px #f87171; }

.sidebar-section-title { font-size:0.68rem !important; font-weight:600 !important;
    text-transform:uppercase !important; letter-spacing:1px !important;
    color:#6a9ec2 !important; padding:12px 0 6px !important; margin:0 !important; }

[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.06) !important; border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius:8px !important; color:#c8ddf0 !important; font-size:0.78rem !important;
    text-align:left !important; padding:8px 12px !important; transition:all 0.2s !important;
    line-height:1.35 !important; height:auto !important; white-space:normal !important; }
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.13) !important; color:#fff !important; transform: translateX(3px) !important; }

.main-header { background: linear-gradient(135deg, #0d2b4e 0%, #1a5276 50%, #1f618d 100%);
    border-radius: 16px; padding: 24px 32px; margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(13,43,78,0.25);
    display:flex; align-items:center; justify-content:space-between; }
.main-header-left { display:flex; align-items:center; gap:16px; }
.main-header-icon { width:56px; height:56px; background: linear-gradient(135deg, #e8b84b, #f5d87a);
    border-radius:14px; display:flex; align-items:center; justify-content:center;
    font-size:28px; box-shadow:0 4px 12px rgba(0,0,0,0.2); }
.main-header h1 { margin:0 !important; font-size:1.45rem !important; color:#fff !important; }
.main-header p { margin:4px 0 0 !important; font-size:0.85rem !important; color:#8ab4d8 !important; }
.header-badge { background: rgba(74,222,128,0.15); border: 1px solid rgba(74,222,128,0.35);
    border-radius:20px; padding:6px 14px; font-size:0.75rem; color:#4ade80; font-weight:600; }

.msg-user { display:flex; justify-content:flex-end; margin:8px 0; }
.msg-user-bubble { background: linear-gradient(135deg, #1a5276, #2471a3);
    color:#fff !important; border-radius:18px 4px 18px 18px;
    padding:12px 18px; max-width:72%; font-size:0.92rem; line-height:1.55;
    box-shadow:0 2px 8px rgba(26,82,118,0.3); }

.msg-agent { display:flex; align-items:flex-start; gap:10px; margin:8px 0; }
.msg-agent-avatar { width:34px; height:34px; flex-shrink:0;
    background: linear-gradient(135deg, #e8b84b, #f5d87a);
    border-radius:50%; display:flex; align-items:center; justify-content:center;
    font-size:16px; box-shadow:0 2px 6px rgba(0,0,0,0.15); margin-top:2px; }
.msg-agent-bubble { background:#fff; border-radius:4px 18px 18px 18px;
    padding:14px 18px; max-width:82%; font-size:0.92rem; line-height:1.6;
    color:#1a1a2e; box-shadow:0 2px 10px rgba(0,0,0,0.07); border:1px solid #e8ecf1; }
.msg-agent-bubble h1, .msg-agent-bubble h2, .msg-agent-bubble h3 {
    color:#0d2b4e !important; margin:14px 0 6px !important; font-size:1rem !important; }
.msg-agent-bubble strong { color:#0d2b4e !important; }
.msg-agent-bubble code { background:#f0f4f8; border-radius:4px;
    padding:1px 5px; font-size:0.85em; color:#c0392b; }

.citation { display:inline-block; background:#eef3f8;
    border:1px solid #c5d8ea; border-radius:6px;
    padding:1px 8px; font-size:0.75rem; color:#1a5276; font-weight:500; margin:2px; }

[data-testid="stChatInput"] { background:#fff !important;
    border:2px solid #d0dcea !important; border-radius:14px !important;
    box-shadow:0 2px 12px rgba(0,0,0,0.06) !important; }
[data-testid="stChatInput"]:focus-within { border-color:#1a5276 !important;
    box-shadow:0 2px 16px rgba(26,82,118,0.15) !important; }

::-webkit-scrollbar { width:5px; height:5px; }
::-webkit-scrollbar-thumb { background:#c5d0de; border-radius:10px; }

.no-config-wrap { display:flex; flex-direction:column;
    align-items:center; justify-content:center;
    min-height:60vh; text-align:center; padding:2rem; }
.no-config-icon { font-size:4rem; margin-bottom:16px; }
.no-config-wrap h2 { color:#0d2b4e !important; font-size:1.6rem !important;
    font-weight:700 !important; margin:0 0 8px !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# ESTADO
# ─────────────────────────────────────────────────────────────────────────────
def _secreto(clave: str) -> str | None:
    try:
        v = st.secrets.get(clave)
        if v:
            return v
    except Exception:
        pass
    return os.environ.get(clave)


# ─────────────────────────────────────────────────────────────────────────────
# AUTENTICACION — pantalla de login con contraseña
# ─────────────────────────────────────────────────────────────────────────────
def _check_password() -> bool:
    """
    Pantalla de login simple. La contraseña se configura en:
      - Streamlit Cloud: Settings → Secrets → APP_PASSWORD
      - Local:           .streamlit/secrets.toml → APP_PASSWORD

    Si no hay APP_PASSWORD configurada, NO bloquea el acceso (modo desarrollo).
    """
    password_correcta = _secreto("APP_PASSWORD")

    # Modo desarrollo: sin contraseña configurada, acceso libre
    if not password_correcta:
        return True

    # Ya autenticado en esta sesión
    if st.session_state.get("autenticado"):
        return True

    # Pantalla de login
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    .login-wrap {
        display:flex; flex-direction:column; align-items:center; justify-content:center;
        min-height: 78vh; padding: 2rem;
    }
    .login-icon {
        width:78px; height:78px;
        background: linear-gradient(135deg, #e8b84b, #f5d87a);
        border-radius:18px;
        display:flex; align-items:center; justify-content:center;
        font-size:38px; box-shadow:0 4px 16px rgba(13,43,78,0.2);
        margin-bottom: 18px;
    }
    .login-title {
        color:#0d2b4e !important; font-size:1.6rem !important;
        font-weight:700 !important; margin:0 0 4px !important;
    }
    .login-sub {
        color:#5a7a9e; font-size:0.92rem; margin:0 0 28px;
        text-align:center; max-width: 380px;
    }
    .login-card {
        background:#fff; border-radius:14px; padding:28px 32px;
        border:1px solid #e0e7ef;
        box-shadow:0 4px 20px rgba(13,43,78,0.08);
        width: 100%; max-width: 380px;
    }
    .login-footer {
        margin-top: 24px; font-size:0.75rem; color:#7a96b3; text-align:center;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="login-wrap">
        <div class="login-icon">🛣️</div>
        <h1 class="login-title">Agente MOP</h1>
        <p class="login-sub">
            Manual de Carreteras de Chile · Ministerio de Obras Públicas<br>
            Ingresa la contraseña proporcionada por tu administrador.
        </p>
    </div>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("login_form", clear_on_submit=False):
            password = st.text_input(
                "Contraseña",
                type="password",
                placeholder="Ingresa tu contraseña",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Acceder", use_container_width=True, type="primary")

            if submitted:
                # hmac.compare_digest evita ataques de timing
                if hmac.compare_digest(password, str(password_correcta)):
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("❌ Contraseña incorrecta")

    st.markdown(
        '<div class="login-footer">Ministerio de Obras Públicas · Chile · Acceso restringido</div>',
        unsafe_allow_html=True,
    )
    return False


def _init():
    if "mensajes_ui" not in st.session_state:
        # Cada msg: {"role": "user"|"assistant", "content": str, "archivos": [str]}
        st.session_state.mensajes_ui = []
    if "api_messages" not in st.session_state:
        st.session_state.api_messages = []          # historial para la API (incluye tool_use/result)
    if "archivos" not in st.session_state:
        st.session_state.archivos = []              # rutas de TODOS los archivos generados (sidebar)
    if "client" not in st.session_state:
        api_key = _secreto("ANTHROPIC_API_KEY")
        if api_key:
            st.session_state.client = anthropic.Anthropic(api_key=api_key)
            st.session_state.api_ok = True
        else:
            st.session_state.client = None
            st.session_state.api_ok = False


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
def _sidebar():
    with st.sidebar:
        st.markdown("""
        <div class="mop-logo-wrap">
            <div class="mop-logo-icon">🛣️</div>
            <div class="mop-logo-text">
                <h2>Agente MOP</h2>
                <p>Manual de Carreteras · Chile</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()
        st.markdown('<p class="sidebar-section-title">Estado del sistema</p>', unsafe_allow_html=True)

        api_dot = "dot-green" if st.session_state.get("api_ok") else "dot-red"
        api_txt = f"Claude {MODELO_CLAUDE.replace('claude-', '').replace('-', ' ').title()}" \
            if st.session_state.get("api_ok") else "API no configurada"
        chroma_ok = (Path(__file__).parent / "chroma_db").exists()

        st.markdown(f"""
        <div class="status-badge"><div class="status-dot {api_dot}"></div><span>{api_txt}</span></div>
        <div class="status-badge"><div class="status-dot {'dot-green' if chroma_ok else 'dot-red'}"></div>
            <span>{'31,952 fragmentos · 86 codigos de señales' if chroma_ok else 'Base de datos no encontrada'}</span></div>
        <div class="status-badge"><div class="status-dot dot-green"></div>
            <span>Prompt caching activo</span></div>
        """, unsafe_allow_html=True)

        st.divider()
        if st.button("＋ Nueva conversación", use_container_width=True):
            st.session_state.mensajes_ui = []
            st.session_state.api_messages = []
            st.session_state.archivos = []
            st.rerun()

        st.divider()
        st.markdown('<p class="sidebar-section-title">Consultas de ejemplo</p>', unsafe_allow_html=True)
        for ej in EJEMPLOS:
            if st.button(ej, key=f"ej_{hash(ej)}", use_container_width=True):
                st.session_state._ejemplo = ej
                st.rerun()

        if st.session_state.archivos:
            st.divider()
            st.markdown('<p class="sidebar-section-title">Archivos generados</p>', unsafe_allow_html=True)
            for ruta in st.session_state.archivos:
                p = Path(ruta)
                if p.exists():
                    with open(p, "rb") as f:
                        datos = f.read()
                    icono = "📊" if p.suffix == ".xlsx" else "📄"
                    mime = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            if p.suffix == ".xlsx" else
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                    st.download_button(f"{icono} {p.name}", data=datos, file_name=p.name,
                                       mime=mime, use_container_width=True, key=f"sdl_{p.name}")

        st.divider()
        st.markdown(
            '<p style="font-size:0.7rem;color:#4a7090;padding:4px 0;">'
            'Ministerio de Obras Públicas · Chile<br>'
            f'Powered by {MODELO_CLAUDE}</p>',
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# RENDERIZADO
# ─────────────────────────────────────────────────────────────────────────────
def _md_a_html(texto: str) -> str:
    import html
    t = html.escape(texto)
    t = re.sub(r'^### (.+)$', r'<h3>\1</h3>', t, flags=re.MULTILINE)
    t = re.sub(r'^## (.+)$',  r'<h2>\1</h2>', t, flags=re.MULTILINE)
    t = re.sub(r'^# (.+)$',   r'<h1>\1</h1>', t, flags=re.MULTILINE)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'\*(.+?)\*',     r'<em>\1</em>', t)
    t = re.sub(r'^[-•] (.+)$', r'<li>\1</li>', t, flags=re.MULTILINE)
    t = re.sub(r'`(.+?)`', r'<code>\1</code>', t)
    t = re.sub(r'\(Manual MOP,([^)]+)\)',
               r'<span class="citation">📖 Manual MOP,\1</span>', t)
    t = t.replace('\n\n', '</p><p>').replace('\n', '<br>')
    return f"<p>{t}</p>"


_ICONOS_EXT = {".xlsx": "📊", ".docx": "📄", ".pdf": "📕"}
_NOMBRE_EXT = {".xlsx": "Excel", ".docx": "Word", ".pdf": "PDF"}
_MIMES = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf":  "application/pdf",
}


def _detectar_archivos_en_texto(texto: str) -> list[str]:
    """
    Fallback: detecta nombres de archivos (xlsx/docx/pdf) mencionados en el
    texto y los resuelve contra la carpeta de reportes. Sirve para mensajes
    antiguos del historial que no guardaron el campo 'archivos'.
    """
    try:
        from mop_config import REPORTS_DIR
    except Exception:
        return []
    encontrados = []
    # 1. Capturar rutas absolutas dentro del texto
    for m in re.finditer(r"([A-Za-z]:\\[^\s\"'`]+?\.(?:xlsx|docx|pdf))", texto):
        ruta = m.group(1)
        if Path(ruta).exists() and ruta not in encontrados:
            encontrados.append(ruta)
    # 2. Capturar nombres de archivo "xxx.xlsx" y buscarlos en REPORTS_DIR
    for m in re.finditer(r"([\w\-]+\.(?:xlsx|docx|pdf))", texto):
        nombre = m.group(1)
        candidata = REPORTS_DIR / nombre
        if candidata.exists() and str(candidata) not in encontrados:
            encontrados.append(str(candidata))
    return encontrados


def _panel_descarga(rutas: list[str], key_suffix: str, destacado: bool = False):
    """
    Panel verde y destacado con botones de descarga grandes. Imposible de
    pasar por alto en la conversacion.
    """
    if not rutas:
        return

    if destacado:
        st.markdown(
            '<div style="margin:10px 0 6px 44px;">'
            '<div style="display:inline-block; background:#dcfce7;'
            ' border:1.5px solid #16a34a; border-radius:10px;'
            ' padding:10px 16px; font-size:0.88rem; color:#14532d;">'
            f'<strong>✅ Archivo{"s" if len(rutas) > 1 else ""} listo{"s" if len(rutas) > 1 else ""} para descargar</strong>'
            '</div></div>',
            unsafe_allow_html=True,
        )

    # Indentado para que se alinee con la burbuja del agente
    cols_wrap = st.container()
    with cols_wrap:
        # Padding-left simulado con columnas
        _, contenido = st.columns([0.04, 0.96])
        with contenido:
            for ruta in rutas:
                p = Path(ruta)
                if not p.exists():
                    st.warning(f"⚠️ Archivo no encontrado: {p.name}")
                    continue
                with open(p, "rb") as f:
                    datos = f.read()
                ext = p.suffix.lower()
                icono = _ICONOS_EXT.get(ext, "📎")
                tipo = _NOMBRE_EXT.get(ext, "Archivo")
                mime = _MIMES.get(ext, "application/octet-stream")
                tam_kb = round(len(datos) / 1024, 1)
                st.download_button(
                    label=f"{icono}   Descargar {tipo}:  {p.name}   ·   {tam_kb} KB",
                    data=datos,
                    file_name=p.name,
                    mime=mime,
                    key=f"dl_{key_suffix}_{p.stem}_{p.suffix}",
                    use_container_width=True,
                    type="primary" if destacado else "secondary",
                )


def _render_historial():
    for i, msg in enumerate(st.session_state.mensajes_ui):
        if msg["role"] == "user":
            st.markdown(
                f'<div class="msg-user"><div class="msg-user-bubble">{msg["content"]}</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f"""
            <div class="msg-agent">
                <div class="msg-agent-avatar">🛣️</div>
                <div class="msg-agent-bubble">{_md_a_html(msg["content"])}</div>
            </div>""", unsafe_allow_html=True)

            # Archivos asociados al mensaje (campo explícito)
            archivos = list(msg.get("archivos", []) or [])

            # Fallback: si el mensaje no tiene 'archivos' pero el texto
            # menciona archivos generados, intentar resolverlos
            if not archivos:
                detectados = _detectar_archivos_en_texto(msg["content"])
                if detectados:
                    archivos = detectados
                    # Guardar para próximos renders y para el sidebar
                    msg["archivos"] = detectados
                    for r in detectados:
                        if r not in st.session_state.archivos:
                            st.session_state.archivos.append(r)

            _panel_descarga(archivos, key_suffix=f"hist_{i}", destacado=True)


def _bienvenida():
    st.markdown("""
    <div class="msg-agent">
        <div class="msg-agent-avatar">🛣️</div>
        <div class="msg-agent-bubble">
            <strong style="color:#0d2b4e;">¡Hola! Soy el Agente MOP.</strong>
            <p>Tengo acceso a los <strong>9 volúmenes completos</strong> del Manual de Carreteras
            (Edición Jun. 2025), con <strong>31.952 fragmentos indexados</strong> y una
            <strong>base estructurada de 86 códigos de señales</strong> con precisión 100%.</p>
            <p>Puedo:</p>
            <ul>
                <li>Responder consultas técnicas con citas exactas (volumen y página)</li>
                <li>Listar códigos y nombres de señales del manual</li>
                <li>Generar archivos Excel con tablas y comparativos</li>
                <li>Crear informes en Word</li>
            </ul>
            <p style="font-size:0.85rem;color:#666;">
                Usa los ejemplos del panel izquierdo o escribe tu consulta directamente.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# LLAMADA A CLAUDE — con prompt caching, adaptive thinking y tool use
# ─────────────────────────────────────────────────────────────────────────────
def _call_claude_stream(client: anthropic.Anthropic):
    """
    Envuelve client.messages.stream(...) con la configuración estándar:
    - Adaptive thinking (el modelo decide cuánto razonar).
    - Prompt caching automático sobre system + tools (ahorro ~90% en turnos
      siguientes mientras el system/tools no cambien).
    - Streaming obligatorio para evitar timeouts en outputs largos.
    """
    return client.messages.stream(
        model=MODELO_CLAUDE,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        # cache_control top-level cachea el último bloque cacheable
        # (tools + system) — los mensajes son volátiles y no se cachean.
        cache_control={"type": "ephemeral"},
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=st.session_state.api_messages,
    )


def _procesar(consulta: str):
    # 1. Burbuja del usuario
    st.markdown(f'<div class="msg-user"><div class="msg-user-bubble">{consulta}</div></div>',
                unsafe_allow_html=True)

    # 2. Agregar al historial de API
    st.session_state.api_messages.append({"role": "user", "content": consulta})

    contenedor = st.empty()
    estado = st.empty()
    archivos_nuevos = []
    respuesta_final = ""
    client = st.session_state.client

    # 3. Loop de tool use con streaming
    MAX_ITER = 12
    for _ in range(MAX_ITER):
        try:
            estado.info("🤖 Consultando a Claude...")
            with _call_claude_stream(client) as stream:
                # Mostrar texto a medida que llega
                texto_actual = ""
                for text in stream.text_stream:
                    texto_actual += text
                    contenedor.markdown(f"""
                    <div class="msg-agent">
                        <div class="msg-agent-avatar">🛣️</div>
                        <div class="msg-agent-bubble">{_md_a_html(texto_actual)}<span style="opacity:.4">▌</span></div>
                    </div>""", unsafe_allow_html=True)

                response = stream.get_final_message()

        except anthropic.RateLimitError:
            estado.empty()
            contenedor.error(
                "⏳ **Límite de velocidad alcanzado**\n\n"
                "Espera unos segundos e intenta de nuevo."
            )
            return
        except anthropic.AuthenticationError:
            estado.empty()
            contenedor.error(
                "🔑 **API Key inválida**\n\n"
                "Verifica `ANTHROPIC_API_KEY` en `.env` o en Streamlit secrets."
            )
            return
        except anthropic.BadRequestError as e:
            estado.empty()
            contenedor.error(f"⚠️ Error de solicitud: ```\n{str(e)[:400]}\n```")
            return
        except Exception as e:
            estado.empty()
            contenedor.error(f"⚠️ Error: ```\n{str(e)[:400]}\n```")
            return

        # Agregar respuesta del assistant al historial de API (con tool_use blocks)
        st.session_state.api_messages.append({"role": "assistant", "content": response.content})

        # Procesar bloques de texto y tool_use
        text_blocks = [b for b in response.content if b.type == "text"]
        tool_uses = [b for b in response.content if b.type == "tool_use"]

        if text_blocks:
            respuesta_final = "\n".join(b.text for b in text_blocks)
            contenedor.markdown(f"""
            <div class="msg-agent">
                <div class="msg-agent-avatar">🛣️</div>
                <div class="msg-agent-bubble">{_md_a_html(respuesta_final)}</div>
            </div>""", unsafe_allow_html=True)

        # Si terminó (sin tool calls), salir
        if response.stop_reason == "end_turn" or not tool_uses:
            break

        # Ejecutar herramientas
        iconos = {
            "buscar_en_manual":       "🔍 Buscando en el manual...",
            "listar_codigos_senales": "📋 Consultando base estructurada de señales...",
            "listar_volumenes":       "📚 Listando volúmenes...",
            "generar_excel":          "📊 Generando Excel...",
            "generar_reporte":        "📄 Generando Word...",
            "generar_pdf":            "📕 Generando PDF...",
        }
        tool_results = []
        for tb in tool_uses:
            estado.info(iconos.get(tb.name, f"⚙️ Ejecutando {tb.name}..."))
            resultado = dispatch_tool(tb.name, tb.input)

            # Detección robusta de archivos generados:
            # match formatos "Excel generado correctamente: <path>",
            # "Reporte Word generado correctamente: <path>", "PDF generado correctamente: <path>"
            m = re.search(
                r"(?:Excel|Reporte Word|PDF|Reporte|Archivo)\s+generado correctamente:\s*(.+?\.(?:xlsx|docx|pdf))",
                resultado, flags=re.IGNORECASE,
            )
            if m:
                ruta_str = m.group(1).strip().strip('"').strip("'")
                p = Path(ruta_str)
                if p.exists():
                    if str(p) not in st.session_state.archivos:
                        st.session_state.archivos.append(str(p))
                    if str(p) not in archivos_nuevos:
                        archivos_nuevos.append(str(p))
                else:
                    # Fallback: intentar como ruta relativa a REPORTS_DIR
                    try:
                        from mop_config import REPORTS_DIR
                        alt = REPORTS_DIR / p.name
                        if alt.exists():
                            if str(alt) not in st.session_state.archivos:
                                st.session_state.archivos.append(str(alt))
                            if str(alt) not in archivos_nuevos:
                                archivos_nuevos.append(str(alt))
                    except Exception:
                        pass

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tb.id,
                "content": resultado,
            })

        st.session_state.api_messages.append({"role": "user", "content": tool_results})

    estado.empty()

    # 4. Panel destacado de descarga (visible antes del rerun)
    _panel_descarga(
        archivos_nuevos,
        key_suffix=f"new_{len(st.session_state.mensajes_ui)}",
        destacado=True,
    )

    # 5. Guardar en historial UI (con los archivos para mostrarlos en futuros renders)
    st.session_state.mensajes_ui.append({"role": "user", "content": consulta, "archivos": []})
    st.session_state.mensajes_ui.append({
        "role": "assistant",
        "content": respuesta_final,
        "archivos": archivos_nuevos,
    })


# ─────────────────────────────────────────────────────────────────────────────
# PANTALLA SIN API
# ─────────────────────────────────────────────────────────────────────────────
def _pantalla_sin_config():
    st.markdown("""
    <div class="no-config-wrap">
        <div class="no-config-icon">🔒</div>
        <h2>Agente MOP</h2>
        <p style="color:#666;max-width:420px;">
            Este agente requiere una clave API de Anthropic configurada por el administrador.
        </p>
        <div style="background:#fff;border-radius:14px;padding:20px 28px;margin-top:20px;
                    border:1px solid #e0e7ef;font-size:0.85rem;color:#444;max-width:420px;">
            <strong style="color:#0d2b4e;">¿Eres el administrador?</strong><br><br>
            Agrega <code>ANTHROPIC_API_KEY=sk-ant-...</code> al archivo <code>.env</code><br>
            o configúralo en Streamlit Secrets.<br><br>
            Obtén tu clave en
            <a href="https://console.anthropic.com" target="_blank" style="color:#1a5276;">
                console.anthropic.com</a>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    # 0. Login obligatorio si APP_PASSWORD está configurado
    if not _check_password():
        return

    # 0.5. Inicializar (o reutilizar de cache) los recursos pesados
    # de ChromaDB + embedding model. Esto evita OOM en Streamlit Cloud.
    _init_recursos_compartidos()

    _init()
    _sidebar()

    if not st.session_state.get("api_ok"):
        _pantalla_sin_config()
        return

    nombre_modelo = MODELO_CLAUDE.replace("claude-", "Claude ").replace("-", " ").title()
    st.markdown(f"""
    <div class="main-header">
        <div class="main-header-left">
            <div class="main-header-icon">🛣️</div>
            <div>
                <h1>Agente MOP — Manual de Carreteras de Chile</h1>
                <p>Powered by {nombre_modelo} · Ministerio de Obras Públicas · Edición Jun. 2025</p>
            </div>
        </div>
        <div class="header-badge">● En línea</div>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.mensajes_ui:
        _bienvenida()
    else:
        _render_historial()

    ejemplo = getattr(st.session_state, "_ejemplo", None)
    if ejemplo:
        del st.session_state._ejemplo
        _procesar(ejemplo)
        st.rerun()

    user_input = st.chat_input("Consulta el Manual de Carreteras de Chile...")
    if user_input:
        _procesar(user_input)
        st.rerun()


if __name__ == "__main__":
    main()
