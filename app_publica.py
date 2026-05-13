import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from groq import Groq
from config import REPORTS_DIR
from agent import generar_excel, generar_reporte
from local_agent import buscar_contexto, construir_prompt_con_contexto, detectar_solicitud_archivo

try:
    from cloud_agent import buscar_en_pinecone, verificar_pinecone
    PINECONE_DISPONIBLE = True
except ImportError:
    PINECONE_DISPONIBLE = False

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agente MOP — Manual de Carreteras",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS GLOBAL
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Google Font ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Reset & base ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* ── Fondo general ── */
.stApp {
    background: #f4f6fa;
}

/* ── Ocultar barra superior de Streamlit ── */
#MainMenu, footer, header { visibility: hidden; }

/* ══════════════════════════════════════════
   SIDEBAR
══════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d2b4e 0%, #1a4a7a 100%) !important;
    border-right: none !important;
}
[data-testid="stSidebar"] * { color: #e8eef5 !important; }
[data-testid="stSidebar"] .stDivider { border-color: rgba(255,255,255,0.12) !important; }

/* Logo MOP */
.mop-logo-wrap {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 18px 16px 8px;
}
.mop-logo-icon {
    width: 44px; height: 44px;
    background: linear-gradient(135deg, #e8b84b, #f0d080);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
.mop-logo-text h2 {
    margin: 0 !important; font-size: 1rem !important;
    font-weight: 700 !important; color: #fff !important;
    line-height: 1.2 !important;
}
.mop-logo-text p {
    margin: 0 !important; font-size: 0.72rem !important;
    color: #8ab0d4 !important; line-height: 1.3 !important;
}

/* Badge de estado */
.status-badge {
    display: flex; align-items: center; gap: 8px;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px; padding: 8px 12px; margin: 4px 0;
    font-size: 0.8rem;
}
.status-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.dot-green  { background:#4ade80; box-shadow:0 0 6px #4ade80; }
.dot-red    { background:#f87171; box-shadow:0 0 6px #f87171; }
.dot-yellow { background:#fbbf24; box-shadow:0 0 6px #fbbf24; }

/* Sección sidebar */
.sidebar-section-title {
    font-size: 0.68rem !important; font-weight: 600 !important;
    text-transform: uppercase !important; letter-spacing: 1px !important;
    color: #6a9ec2 !important; padding: 12px 0 6px !important;
    margin: 0 !important;
}

/* Botones de ejemplo */
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important; color: #c8ddf0 !important;
    font-size: 0.78rem !important; text-align: left !important;
    padding: 8px 12px !important; margin: 2px 0 !important;
    transition: all 0.2s !important; line-height: 1.35 !important;
    height: auto !important; white-space: normal !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.13) !important;
    border-color: rgba(255,255,255,0.25) !important;
    color: #fff !important; transform: translateX(3px) !important;
}

/* Botón nueva conversación */
.btn-nueva button {
    background: rgba(74,222,128,0.12) !important;
    border: 1px solid rgba(74,222,128,0.3) !important;
    color: #4ade80 !important; font-weight: 600 !important;
    font-size: 0.8rem !important; border-radius: 8px !important;
    padding: 8px 12px !important;
}
.btn-nueva button:hover {
    background: rgba(74,222,128,0.2) !important;
}

/* Botones de descarga sidebar */
[data-testid="stSidebar"] .stDownloadButton > button {
    background: rgba(232,184,75,0.15) !important;
    border: 1px solid rgba(232,184,75,0.3) !important;
    color: #e8b84b !important; font-size: 0.78rem !important;
    border-radius: 8px !important; text-align: left !important;
}

/* ══════════════════════════════════════════
   ÁREA PRINCIPAL — HEADER
══════════════════════════════════════════ */
.main-header {
    background: linear-gradient(135deg, #0d2b4e 0%, #1a5276 50%, #1f618d 100%);
    border-radius: 16px; padding: 24px 32px; margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(13,43,78,0.25);
    display: flex; align-items: center; justify-content: space-between;
}
.main-header-left { display: flex; align-items: center; gap: 16px; }
.main-header-icon {
    width: 56px; height: 56px;
    background: linear-gradient(135deg, #e8b84b, #f5d87a);
    border-radius: 14px; display: flex;
    align-items: center; justify-content: center;
    font-size: 28px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    flex-shrink: 0;
}
.main-header h1 {
    margin: 0 !important; font-size: 1.45rem !important;
    font-weight: 700 !important; color: #fff !important;
    line-height: 1.2 !important;
}
.main-header p {
    margin: 4px 0 0 !important; font-size: 0.85rem !important;
    color: #8ab4d8 !important;
}
.header-badge {
    background: rgba(74,222,128,0.15);
    border: 1px solid rgba(74,222,128,0.35);
    border-radius: 20px; padding: 6px 14px;
    font-size: 0.75rem; color: #4ade80; font-weight: 600;
    white-space: nowrap;
}

/* ══════════════════════════════════════════
   CHAT — MENSAJES
══════════════════════════════════════════ */

/* Ocultar avatares por defecto de Streamlit */
[data-testid="stChatMessage"] [data-testid="chatAvatarIcon-user"],
[data-testid="stChatMessage"] [data-testid="chatAvatarIcon-assistant"] {
    display: none !important;
}

/* Contenedor de mensaje */
[data-testid="stChatMessage"] {
    background: transparent !important;
    padding: 4px 0 !important;
    border: none !important;
}

/* Burbuja usuario */
.msg-user {
    display: flex; justify-content: flex-end; margin: 8px 0;
}
.msg-user-bubble {
    background: linear-gradient(135deg, #1a5276, #2471a3);
    color: #fff !important; border-radius: 18px 4px 18px 18px;
    padding: 12px 18px; max-width: 72%; font-size: 0.92rem;
    line-height: 1.55; box-shadow: 0 2px 8px rgba(26,82,118,0.3);
}

/* Burbuja agente */
.msg-agent {
    display: flex; align-items: flex-start; gap: 10px; margin: 8px 0;
}
.msg-agent-avatar {
    width: 34px; height: 34px; flex-shrink: 0;
    background: linear-gradient(135deg, #e8b84b, #f5d87a);
    border-radius: 50%; display: flex;
    align-items: center; justify-content: center; font-size: 16px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.15); margin-top: 2px;
}
.msg-agent-bubble {
    background: #fff; border-radius: 4px 18px 18px 18px;
    padding: 14px 18px; max-width: 82%;
    font-size: 0.92rem; line-height: 1.6; color: #1a1a2e;
    box-shadow: 0 2px 10px rgba(0,0,0,0.07);
    border: 1px solid #e8ecf1;
}
.msg-agent-bubble p { margin: 0 0 8px !important; }
.msg-agent-bubble p:last-child { margin-bottom: 0 !important; }
.msg-agent-bubble h1,.msg-agent-bubble h2,.msg-agent-bubble h3 {
    color: #0d2b4e !important; margin: 14px 0 6px !important;
    font-size: 1rem !important;
}
.msg-agent-bubble ul, .msg-agent-bubble ol {
    padding-left: 20px !important; margin: 6px 0 !important;
}
.msg-agent-bubble li { margin: 3px 0 !important; }
.msg-agent-bubble strong { color: #0d2b4e !important; }
.msg-agent-bubble code {
    background: #f0f4f8; border-radius: 4px;
    padding: 1px 5px; font-size: 0.85em; color: #c0392b;
}

/* ══════════════════════════════════════════
   WELCOME CARD
══════════════════════════════════════════ */
.welcome-card {
    background: #fff; border-radius: 16px; padding: 28px 32px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07); border: 1px solid #e8ecf1;
    margin: 8px 0 16px;
}
.welcome-card h3 {
    color: #0d2b4e !important; margin: 0 0 8px !important;
    font-size: 1.1rem !important; font-weight: 600 !important;
}
.welcome-card p {
    color: #555 !important; font-size: 0.9rem !important;
    line-height: 1.6 !important; margin: 0 0 16px !important;
}
.caps-grid {
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 10px; margin-top: 8px;
}
.cap-item {
    display: flex; align-items: flex-start; gap: 10px;
    background: #f8fafc; border-radius: 10px; padding: 12px 14px;
    border: 1px solid #e8ecf1;
}
.cap-icon {
    font-size: 1.3rem; flex-shrink: 0; margin-top: 1px;
}
.cap-text strong { display: block; font-size: 0.82rem; color: #0d2b4e; }
.cap-text span { font-size: 0.76rem; color: #777; }

/* ══════════════════════════════════════════
   CITATION TAG
══════════════════════════════════════════ */
.citation {
    display: inline-block; background: #eef3f8;
    border: 1px solid #c5d8ea; border-radius: 6px;
    padding: 1px 8px; font-size: 0.75rem; color: #1a5276;
    font-weight: 500; margin: 2px;
}

/* ══════════════════════════════════════════
   BOTÓN DESCARGA EN CHAT
══════════════════════════════════════════ */
.download-wrapper {
    margin-top: 12px; padding-top: 12px;
    border-top: 1px solid #eef1f5;
}
.download-wrapper .stDownloadButton > button {
    background: linear-gradient(135deg, #0d2b4e, #1a5276) !important;
    color: #fff !important; border: none !important;
    border-radius: 10px !important; font-weight: 600 !important;
    font-size: 0.82rem !important; padding: 8px 18px !important;
    box-shadow: 0 2px 8px rgba(13,43,78,0.25) !important;
    transition: all 0.2s !important;
}
.download-wrapper .stDownloadButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(13,43,78,0.35) !important;
}

/* ══════════════════════════════════════════
   CHAT INPUT
══════════════════════════════════════════ */
[data-testid="stChatInput"] {
    background: #fff !important;
    border: 2px solid #d0dcea !important;
    border-radius: 14px !important;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06) !important;
    transition: border-color 0.2s !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: #1a5276 !important;
    box-shadow: 0 2px 16px rgba(26,82,118,0.15) !important;
}
[data-testid="stChatInput"] textarea {
    font-size: 0.92rem !important; color: #1a1a2e !important;
}

/* ══════════════════════════════════════════
   SIN CONFIGURACIÓN
══════════════════════════════════════════ */
.no-config-wrap {
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    min-height: 60vh; text-align: center; padding: 2rem;
}
.no-config-icon {
    font-size: 4rem; margin-bottom: 16px;
    animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
    0%,100% { transform: scale(1); }
    50% { transform: scale(1.08); }
}
.no-config-wrap h2 {
    color: #0d2b4e !important; font-size: 1.6rem !important;
    font-weight: 700 !important; margin: 0 0 8px !important;
}
.no-config-wrap p {
    color: #666 !important; font-size: 0.95rem !important;
    max-width: 400px; line-height: 1.6 !important;
}
.no-config-card {
    background: #fff; border-radius: 14px; padding: 20px 28px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    border: 1px solid #e0e7ef; margin-top: 20px;
    font-size: 0.85rem; color: #444;
    max-width: 360px; text-align: left;
}
.no-config-card b { color: #0d2b4e; }

/* ══════════════════════════════════════════
   SPINNER PERSONALIZADO
══════════════════════════════════════════ */
.searching-indicator {
    display: flex; align-items: center; gap: 10px;
    background: #f0f6ff; border: 1px solid #c5d8ea;
    border-radius: 10px; padding: 10px 16px; margin: 6px 0;
    font-size: 0.83rem; color: #1a5276;
}
.dot-pulse {
    display: flex; gap: 4px; align-items: center;
}
.dot-pulse span {
    width: 6px; height: 6px; background: #1a5276;
    border-radius: 50%; animation: dotpulse 1.2s infinite;
}
.dot-pulse span:nth-child(2) { animation-delay: 0.2s; }
.dot-pulse span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotpulse {
    0%,80%,100% { transform: scale(0.7); opacity: 0.4; }
    40% { transform: scale(1); opacity: 1; }
}

/* ══════════════════════════════════════════
   SCROLLBAR
══════════════════════════════════════════ */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #c5d0de; border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: #a0aec0; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────
MODELO_GROQ    = "llama-3.3-70b-versatile"
MODELO_GROQ_RAPIDO = "llama-3.1-8b-instant"  # para tareas auxiliares (JSON)
MAX_HISTORIAL  = 4
N_FRAGMENTOS_RAG = 12  # mucho mas contexto = mejores respuestas

EJEMPLOS = [
    "¿Cuáles son los radios mínimos de curvatura horizontal?",
    "Normas para pavimentos flexibles según el MOP",
    "Criterios de visibilidad de parada en carreteras",
    "Diseño de intersecciones a nivel — requisitos",
    "Valores de peralte máximo permitido",
    "Drenaje superficial en carreteras de montaña",
    "Señalización vertical: tipos y ubicación",
    "Diseño de caminos de bajo volumen de tránsito",
]

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _secreto(clave: str) -> str | None:
    try:
        v = st.secrets.get(clave)
        if v: return v
    except Exception:
        pass
    return os.environ.get(clave)


def _modo() -> str:
    if PINECONE_DISPONIBLE and _secreto("PINECONE_API_KEY"):
        return "pinecone"
    return "local"


def _init():
    if "mensajes"          not in st.session_state: st.session_state.mensajes          = []
    if "archivos"          not in st.session_state: st.session_state.archivos          = []
    if "modo"              not in st.session_state: st.session_state.modo              = _modo()
    if "groq_ok"           not in st.session_state:
        k = _secreto("GROQ_API_KEY")
        st.session_state.groq_ok  = bool(k)
        st.session_state.groq_key = k or ""


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
def _sidebar():
    with st.sidebar:
        # Logo
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

        # Estado del sistema
        st.markdown('<p class="sidebar-section-title">Estado del sistema</p>', unsafe_allow_html=True)

        groq_dot  = "dot-green" if st.session_state.groq_ok else "dot-red"
        groq_txt  = "Groq LLM activo" if st.session_state.groq_ok else "Sin clave Groq"

        chroma_ok = (Path(__file__).parent / "chroma_db").exists()
        bd_dot    = "dot-green" if (st.session_state.modo == "pinecone" or chroma_ok) else "dot-yellow"
        bd_txt    = ("Pinecone Cloud" if st.session_state.modo == "pinecone"
                     else ("ChromaDB local" if chroma_ok else "Base de datos no encontrada"))

        st.markdown(f"""
        <div class="status-badge">
            <div class="status-dot {groq_dot}"></div>
            <span>{groq_txt}</span>
        </div>
        <div class="status-badge">
            <div class="status-dot {bd_dot}"></div>
            <span>{bd_txt}</span>
        </div>
        <div class="status-badge">
            <div class="status-dot dot-green"></div>
            <span>31,952 fragmentos indexados</span>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Nueva conversación
        st.markdown('<div class="btn-nueva">', unsafe_allow_html=True)
        if st.button("＋  Nueva conversación", use_container_width=True, key="btn_nueva"):
            st.session_state.mensajes = []
            st.session_state.archivos = []
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.divider()

        # Ejemplos
        st.markdown('<p class="sidebar-section-title">Consultas de ejemplo</p>', unsafe_allow_html=True)
        for ej in EJEMPLOS:
            if st.button(ej, key=f"ej_{hash(ej)}", use_container_width=True):
                st.session_state._ejemplo = ej
                st.rerun()

        # Archivos generados
        if st.session_state.archivos:
            st.divider()
            st.markdown('<p class="sidebar-section-title">Archivos generados</p>', unsafe_allow_html=True)
            for ruta in st.session_state.archivos:
                p = Path(ruta)
                if p.exists():
                    with open(p, "rb") as f: datos = f.read()
                    icono = "📊" if p.suffix == ".xlsx" else "📄"
                    mime = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            if p.suffix == ".xlsx" else
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                    st.download_button(f"{icono} {p.name}", data=datos,
                                       file_name=p.name, mime=mime,
                                       use_container_width=True, key=f"sdl_{p.name}")

        st.divider()
        st.markdown('<p style="font-size:0.7rem;color:#4a7090;padding:4px 0;">Ministerio de Obras Públicas · Chile<br>Versión Jun. 2025</p>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# PANTALLA SIN CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────
def _pantalla_sin_config():
    st.markdown("""
    <div class="no-config-wrap">
        <div class="no-config-icon">🔒</div>
        <h2>Agente MOP</h2>
        <p>Este agente no está configurado aún.<br>
           Contacta al administrador para obtener acceso.</p>
        <div class="no-config-card">
            <b>¿Eres el administrador?</b><br><br>
            Agrega tu clave de Groq al archivo <code>.env</code>:<br><br>
            <code>GROQ_API_KEY=gsk_tu_clave_aqui</code><br><br>
            Obtén tu clave gratuita en
            <a href="https://console.groq.com/keys" target="_blank"
               style="color:#1a5276;">console.groq.com</a>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# BIENVENIDA
# ─────────────────────────────────────────────────────────────────────────────
def _bienvenida():
    st.markdown("""
    <div class="msg-agent">
        <div class="msg-agent-avatar">🛣️</div>
        <div class="msg-agent-bubble">
            <strong style="color:#0d2b4e;font-size:0.95rem;">
                ¡Hola! Soy el Agente del Manual de Carreteras de Chile.
            </strong>
            <p style="margin:8px 0 0;color:#444;">
                Tengo acceso a los <strong>9 volúmenes completos</strong> del Manual MOP
                (Jun. 2025), con más de 31.000 fragmentos indexados.
                Puedo ayudarte con:
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="welcome-card">
        <div class="caps-grid">
            <div class="cap-item">
                <div class="cap-icon">📐</div>
                <div class="cap-text">
                    <strong>Diseño geométrico</strong>
                    <span>Curvas, pendientes, secciones transversales</span>
                </div>
            </div>
            <div class="cap-item">
                <div class="cap-icon">🏗️</div>
                <div class="cap-text">
                    <strong>Pavimentos</strong>
                    <span>Flexibles, rígidos, dimensionamiento</span>
                </div>
            </div>
            <div class="cap-item">
                <div class="cap-icon">🚦</div>
                <div class="cap-text">
                    <strong>Señalización</strong>
                    <span>Vertical, horizontal, seguridad vial</span>
                </div>
            </div>
            <div class="cap-item">
                <div class="cap-icon">🌊</div>
                <div class="cap-text">
                    <strong>Drenaje e hidrología</strong>
                    <span>Cunetas, alcantarillas, obras de arte</span>
                </div>
            </div>
            <div class="cap-item">
                <div class="cap-icon">🌉</div>
                <div class="cap-text">
                    <strong>Puentes y estructuras</strong>
                    <span>Cargas, diseño, especificaciones</span>
                </div>
            </div>
            <div class="cap-item">
                <div class="cap-icon">📊</div>
                <div class="cap-text">
                    <strong>Reportes y tablas</strong>
                    <span>Excel y Word con datos del manual</span>
                </div>
            </div>
        </div>
        <p style="margin:14px 0 0;font-size:0.8rem;color:#888;">
            💡 Usa los ejemplos del panel izquierdo o escribe tu consulta directamente.
            Cito el volumen y página de cada dato.
        </p>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# RENDERIZAR HISTORIAL
# ─────────────────────────────────────────────────────────────────────────────
def _render_historial():
    for msg in st.session_state.mensajes:
        if msg["role"] == "user":
            st.markdown(f"""
            <div class="msg-user">
                <div class="msg-user-bubble">{msg["content"]}</div>
            </div>""", unsafe_allow_html=True)
        else:
            contenido = msg["content"]
            st.markdown(f"""
            <div class="msg-agent">
                <div class="msg-agent-avatar">🛣️</div>
                <div class="msg-agent-bubble">{_md_a_html(contenido)}</div>
            </div>""", unsafe_allow_html=True)


def _md_a_html(texto: str) -> str:
    """Convierte Markdown básico a HTML para mostrar en burbuja."""
    import html
    t = html.escape(texto)
    # Headers
    t = re.sub(r'^### (.+)$', r'<h3>\1</h3>', t, flags=re.MULTILINE)
    t = re.sub(r'^## (.+)$',  r'<h2>\1</h2>', t, flags=re.MULTILINE)
    t = re.sub(r'^# (.+)$',   r'<h1>\1</h1>', t, flags=re.MULTILINE)
    # Negrita e itálica
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'\*(.+?)\*',     r'<em>\1</em>', t)
    # Listas
    t = re.sub(r'^[-•] (.+)$', r'<li>\1</li>', t, flags=re.MULTILINE)
    t = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', t, flags=re.DOTALL)
    # Code inline
    t = re.sub(r'`(.+?)`', r'<code>\1</code>', t)
    # Citas MOP — highlight automático
    t = re.sub(r'\(Manual MOP,([^)]+)\)',
               r'<span class="citation">📖 Manual MOP,\1</span>', t)
    # Saltos de línea
    t = t.replace('\n\n', '</p><p>').replace('\n', '<br>')
    return f"<p>{t}</p>"


# ─────────────────────────────────────────────────────────────────────────────
# PROCESAR CONSULTA
# ─────────────────────────────────────────────────────────────────────────────
def _procesar(consulta: str):
    # Mostrar burbuja de usuario
    st.markdown(f"""
    <div class="msg-user">
        <div class="msg-user-bubble">{consulta}</div>
    </div>""", unsafe_allow_html=True)

    # Indicador de búsqueda
    buscando = st.empty()
    buscando.markdown("""
    <div class="searching-indicator">
        <div class="dot-pulse">
            <span></span><span></span><span></span>
        </div>
        Buscando en el Manual MOP…
    </div>""", unsafe_allow_html=True)

    # 1. Buscar contexto (multi-query con expansion automatica)
    try:
        if st.session_state.modo == "pinecone":
            fragmentos = buscar_en_pinecone(consulta, api_key=_secreto("PINECONE_API_KEY"))
        else:
            fragmentos = buscar_contexto(consulta, n_resultados=N_FRAGMENTOS_RAG)
    except Exception:
        fragmentos = []

    buscando.markdown("""
    <div class="searching-indicator">
        <div class="dot-pulse">
            <span></span><span></span><span></span>
        </div>
        Generando respuesta…
    </div>""", unsafe_allow_html=True)

    # 2. Construir prompt
    historial_prev = st.session_state.mensajes[-MAX_HISTORIAL:]
    mensajes_api = construir_prompt_con_contexto(
        pregunta=consulta,
        fragmentos=fragmentos,
        historial=historial_prev,
    )

    # 3. Llamar a Groq con streaming + fallback automatico
    respuesta = ""
    contenedor = st.empty()

    # Lista de modelos en orden de preferencia (cae al siguiente si hay rate limit)
    modelos_fallback = [
        ("llama-3.3-70b-versatile", "Llama 3.3 70B"),
        ("llama-3.1-8b-instant",    "Llama 3.1 8B (rapido, mayor cupo)"),
        ("llama-3.2-3b-preview",    "Llama 3.2 3B"),
    ]

    client = Groq(api_key=st.session_state.groq_key)
    stream = None
    modelo_usado = None
    ultimo_error = None

    for modelo_id, modelo_nombre in modelos_fallback:
        try:
            stream = client.chat.completions.create(
                model=modelo_id,
                messages=mensajes_api,
                stream=True,
                temperature=0.3,
                max_tokens=4096,
            )
            modelo_usado = modelo_nombre
            break
        except Exception as e:
            ultimo_error = e
            err_str = str(e).lower()
            # Si NO es rate limit, no tiene sentido reintentar con otro modelo
            if "rate_limit" not in err_str and "429" not in err_str:
                break
            # Si es rate limit, avisar y probar el siguiente
            buscando.warning(f"⚠️ Cupo agotado para {modelo_nombre}. Probando modelo alternativo...")

    if stream is None:
        # Todos los modelos fallaron
        buscando.empty()
        err = str(ultimo_error)[:400] if ultimo_error else "Sin respuesta"
        # Detectar si es rate limit y dar mensaje amigable
        if "rate_limit" in err.lower() or "429" in err:
            contenedor.error(
                f"⚠️ **Cupo diario de Groq agotado**\n\n"
                f"Has usado todo el cupo gratis diario. Opciones:\n\n"
                f"1. **Esperar** (~1-2 horas para que se renueve)\n"
                f"2. **Usar el agente independiente local** (sin tokens, sin límites)\n"
                f"   → Ejecuta: `INICIAR_INDEPENDIENTE.bat` o ve a `http://localhost:8502`\n"
                f"3. **Subir a plan pago de Groq** (developer tier, $9 USD/mes)\n\n"
                f"Detalle: `{err[:200]}`"
            )
        else:
            contenedor.error(f"Error de Groq: ```\n{err}\n```")
        respuesta = "Error: cupo agotado o error de API"
        st.session_state.mensajes.append({"role": "user", "content": consulta})
        st.session_state.mensajes.append({"role": "assistant", "content": respuesta})
        return

    # Continuar con streaming usando el modelo que funciono
    try:
        buscando.empty()
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            respuesta += delta
            contenedor.markdown(f"""
            <div class="msg-agent">
                <div class="msg-agent-avatar">🛣️</div>
                <div class="msg-agent-bubble">{_md_a_html(respuesta)}<span style="opacity:.4">▌</span></div>
            </div>""", unsafe_allow_html=True)

        contenedor.markdown(f"""
        <div class="msg-agent">
            <div class="msg-agent-avatar">🛣️</div>
            <div class="msg-agent-bubble">{_md_a_html(respuesta)}</div>
        </div>""", unsafe_allow_html=True)

    except Exception as e:
        buscando.empty()
        # Mostrar error real con detalle
        import traceback
        error_msg = str(e)[:500]
        contenedor.error(
            f"⚠️ Error al obtener respuesta:\n\n"
            f"```\n{error_msg}\n```\n\n"
            f"💡 Si es un error de contexto, intenta una pregunta más específica."
        )
        respuesta = f"Error: {error_msg}"

    # 4. ¿Generar archivo?
    solicitud = detectar_solicitud_archivo(consulta)
    archivos_nuevos = []

    if solicitud["excel"] or solicitud["word"]:
        col1, col2, _ = st.columns([1, 1, 3])
        if solicitud["excel"] and col1.button("📊 Generar Excel", type="primary",
                                               key=f"gexcel_{len(st.session_state.mensajes)}"):
            with st.spinner("Generando Excel…"):
                try:
                    # Pedir a Groq el JSON
                    jr = Groq(api_key=st.session_state.groq_key).chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=[
                            {"role": "system", "content": "Devuelve SOLO un JSON válido (lista de dicts), sin texto adicional."},
                            {"role": "user",   "content": f"Genera JSON para Excel basado en:\n{respuesta[:2000]}\nConsulta: {consulta}"},
                        ], max_tokens=2000,
                    )
                    m = re.search(r"\[.*\]", jr.choices[0].message.content, re.DOTALL)
                    if m:
                        nombre = "_".join(consulta.split()[:4])
                        res = generar_excel(m.group(), nombre, titulo=consulta[:80])
                        if "correctamente:" in res:
                            p = Path(res.split("correctamente:")[-1].strip())
                            if p.exists():
                                archivos_nuevos.append(p)
                                st.session_state.archivos.append(str(p))
                except Exception as e:
                    st.warning(f"No se pudo generar el Excel: {e}")

        if solicitud["word"] and col2.button("📄 Generar Word",
                                              key=f"gword_{len(st.session_state.mensajes)}"):
            with st.spinner("Generando Word…"):
                try:
                    nombre = "_".join(consulta.split()[:4])
                    res = generar_reporte(respuesta, nombre, titulo=consulta[:80])
                    if "correctamente:" in res:
                        p = Path(res.split("correctamente:")[-1].strip())
                        if p.exists():
                            archivos_nuevos.append(p)
                            st.session_state.archivos.append(str(p))
                except Exception as e:
                    st.warning(f"No se pudo generar el Word: {e}")

    # Botones de descarga inmediatos
    if archivos_nuevos:
        st.markdown('<div class="download-wrapper">', unsafe_allow_html=True)
        for p in archivos_nuevos:
            with open(p, "rb") as f: datos = f.read()
            icono = "📊" if p.suffix == ".xlsx" else "📄"
            mime = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    if p.suffix == ".xlsx" else
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            st.download_button(f"{icono} Descargar {p.name}", data=datos,
                               file_name=p.name, mime=mime,
                               key=f"dl_{p.name}_{len(st.session_state.mensajes)}")
        st.markdown('</div>', unsafe_allow_html=True)

    # Guardar en historial
    st.session_state.mensajes.append({"role": "user",      "content": consulta})
    st.session_state.mensajes.append({"role": "assistant", "content": respuesta})


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    _init()
    _sidebar()

    if not st.session_state.groq_ok:
        _pantalla_sin_config()
        return

    # Header principal
    st.markdown("""
    <div class="main-header">
        <div class="main-header-left">
            <div class="main-header-icon">🛣️</div>
            <div>
                <h1>Agente MOP</h1>
                <p>Manual de Carreteras de Chile · Ministerio de Obras Públicas</p>
            </div>
        </div>
        <div class="header-badge">● En línea</div>
    </div>
    """, unsafe_allow_html=True)

    # Bienvenida o historial
    if not st.session_state.mensajes:
        _bienvenida()
    else:
        _render_historial()

    # Manejar ejemplo desde sidebar
    if hasattr(st.session_state, "_ejemplo") and st.session_state._ejemplo:
        consulta = st.session_state._ejemplo
        del st.session_state._ejemplo
        _procesar(consulta)
        st.rerun()

    # Input del usuario
    user_input = st.chat_input("Consulta el Manual de Carreteras de Chile…")
    if user_input:
        _procesar(user_input)
        st.rerun()


if __name__ == "__main__":
    main()
