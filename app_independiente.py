"""
Agente MOP — Modo INDEPENDIENTE
- Sin tokens, sin internet, sin APIs externas.
- Modelo LLM local via GPT4All.
- Vector store local (ChromaDB).

Uso:
    streamlit run app_independiente.py
"""

import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from pathlib import Path

from local_agent import (
    buscar_contexto,
    construir_prompt_con_contexto,
    detectar_solicitud_archivo,
)
from agent import generar_excel, generar_reporte
from independent_agent import (
    MODELOS_DISPONIBLES,
    MODELO_DEFAULT,
    listar_modelos_descargados,
    descargar_modelo,
    cargar_modelo,
    generar_streaming,
    estado_sistema,
)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agente MOP — Modo Independiente",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Reusa el CSS de app_publica.py
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.stApp { background: #f4f6fa; }
#MainMenu, footer, header { visibility: hidden; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d2b4e 0%, #1a4a7a 100%) !important;
}
[data-testid="stSidebar"] * { color: #e8eef5 !important; }
[data-testid="stSidebar"] .stDivider { border-color: rgba(255,255,255,0.12) !important; }

.mop-logo-wrap { display:flex; align-items:center; gap:12px; padding:18px 16px 8px; }
.mop-logo-icon {
    width:44px; height:44px;
    background: linear-gradient(135deg, #4ade80, #6ee7b7);
    border-radius:10px; display:flex; align-items:center; justify-content:center;
    font-size:22px; box-shadow:0 2px 8px rgba(0,0,0,0.3);
}
.mop-logo-text h2 {
    margin:0 !important; font-size:1rem !important; font-weight:700 !important;
    color:#fff !important; line-height:1.2 !important;
}
.mop-logo-text p {
    margin:0 !important; font-size:0.72rem !important;
    color:#8ab0d4 !important; line-height:1.3 !important;
}

.status-badge {
    display:flex; align-items:center; gap:8px;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius:8px; padding:8px 12px; margin:4px 0;
    font-size:0.8rem;
}
.status-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.dot-green { background:#4ade80; box-shadow:0 0 6px #4ade80; }
.dot-red   { background:#f87171; box-shadow:0 0 6px #f87171; }

.sidebar-section-title {
    font-size:0.68rem !important; font-weight:600 !important;
    text-transform:uppercase !important; letter-spacing:1px !important;
    color:#6a9ec2 !important; padding:12px 0 6px !important; margin:0 !important;
}

[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius:8px !important; color:#c8ddf0 !important;
    font-size:0.78rem !important; text-align:left !important;
    padding:8px 12px !important; transition:all 0.2s !important;
    line-height:1.35 !important; height:auto !important; white-space:normal !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.13) !important;
    border-color: rgba(255,255,255,0.25) !important;
    color:#fff !important; transform: translateX(3px) !important;
}

.main-header {
    background: linear-gradient(135deg, #064e3b 0%, #047857 50%, #059669 100%);
    border-radius: 16px; padding: 24px 32px; margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(6,78,59,0.25);
    display: flex; align-items: center; justify-content: space-between;
}
.main-header-left { display:flex; align-items:center; gap:16px; }
.main-header-icon {
    width:56px; height:56px;
    background: linear-gradient(135deg, #4ade80, #6ee7b7);
    border-radius:14px; display:flex; align-items:center; justify-content:center;
    font-size:28px; box-shadow:0 4px 12px rgba(0,0,0,0.2);
}
.main-header h1 {
    margin:0 !important; font-size:1.45rem !important; font-weight:700 !important;
    color:#fff !important;
}
.main-header p {
    margin:4px 0 0 !important; font-size:0.85rem !important; color:#a7f3d0 !important;
}
.header-badge {
    background: rgba(74,222,128,0.2);
    border: 1px solid rgba(74,222,128,0.5);
    border-radius:20px; padding:6px 14px;
    font-size:0.75rem; color:#fff; font-weight:600;
}

.msg-user { display:flex; justify-content:flex-end; margin:8px 0; }
.msg-user-bubble {
    background: linear-gradient(135deg, #047857, #059669);
    color:#fff !important; border-radius:18px 4px 18px 18px;
    padding:12px 18px; max-width:72%; font-size:0.92rem; line-height:1.55;
    box-shadow:0 2px 8px rgba(4,120,87,0.3);
}

.msg-agent { display:flex; align-items:flex-start; gap:10px; margin:8px 0; }
.msg-agent-avatar {
    width:34px; height:34px; flex-shrink:0;
    background: linear-gradient(135deg, #4ade80, #6ee7b7);
    border-radius:50%; display:flex; align-items:center; justify-content:center;
    font-size:16px; box-shadow:0 2px 6px rgba(0,0,0,0.15); margin-top:2px;
}
.msg-agent-bubble {
    background:#fff; border-radius:4px 18px 18px 18px;
    padding:14px 18px; max-width:82%;
    font-size:0.92rem; line-height:1.6; color:#1a1a2e;
    box-shadow:0 2px 10px rgba(0,0,0,0.07); border:1px solid #e8ecf1;
}
.msg-agent-bubble h1, .msg-agent-bubble h2, .msg-agent-bubble h3 {
    color:#064e3b !important; margin:14px 0 6px !important; font-size:1rem !important;
}
.msg-agent-bubble strong { color:#064e3b !important; }
.msg-agent-bubble code {
    background:#f0f4f8; border-radius:4px;
    padding:1px 5px; font-size:0.85em; color:#c0392b;
}

.welcome-card {
    background:#fff; border-radius:16px; padding:28px 32px;
    box-shadow:0 2px 12px rgba(0,0,0,0.07); border:1px solid #e8ecf1; margin:8px 0;
}
.welcome-card h3 {
    color:#064e3b !important; margin:0 0 8px !important;
    font-size:1.1rem !important; font-weight:600 !important;
}
.welcome-card p { color:#555 !important; font-size:0.9rem !important; line-height:1.6 !important; }

.feature-card {
    background:#f0fdf4; border-left:4px solid #047857;
    border-radius:8px; padding:14px 18px; margin:8px 0; font-size:0.85rem; color:#064e3b;
}
.feature-card strong { color:#047857; }

.modelo-card {
    background:#fff; border:2px solid #e5e7eb; border-radius:12px;
    padding:16px 20px; margin:8px 0; cursor:pointer; transition:all 0.2s;
}
.modelo-card.selected { border-color:#047857; background:#f0fdf4; }
.modelo-card h4 { margin:0; color:#064e3b; font-size:0.95rem; }
.modelo-card p { margin:4px 0 0; font-size:0.8rem; color:#666; }

.citation {
    display:inline-block; background:#d1fae5;
    border:1px solid #6ee7b7; border-radius:6px;
    padding:1px 8px; font-size:0.75rem; color:#064e3b;
    font-weight:500; margin:2px;
}

[data-testid="stChatInput"] {
    background:#fff !important;
    border:2px solid #d0dcea !important;
    border-radius:14px !important;
    box-shadow:0 2px 12px rgba(0,0,0,0.06) !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color:#047857 !important;
    box-shadow:0 2px 16px rgba(4,120,87,0.15) !important;
}

::-webkit-scrollbar { width:5px; height:5px; }
::-webkit-scrollbar-thumb { background:#c5d0de; border-radius:10px; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# ESTADO
# ─────────────────────────────────────────────────────────────────────────────
def _init():
    if "mensajes" not in st.session_state: st.session_state.mensajes = []
    if "archivos" not in st.session_state: st.session_state.archivos = []

    # Limpiar state stale: si el modelo guardado ya no existe en el catalogo
    if "modelo_local" in st.session_state and st.session_state.modelo_local not in MODELOS_DISPONIBLES:
        del st.session_state.modelo_local
    if "_descargar_modelo" in st.session_state and st.session_state._descargar_modelo not in MODELOS_DISPONIBLES:
        del st.session_state._descargar_modelo

    if "modelo_local" not in st.session_state:
        descargados = listar_modelos_descargados()
        st.session_state.modelo_local = descargados[0] if descargados else MODELO_DEFAULT
    if "modelo_listo" not in st.session_state:
        st.session_state.modelo_listo = bool(listar_modelos_descargados())


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
                <p>Modo Independiente · Sin tokens</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Estado
        st.markdown('<p class="sidebar-section-title">Estado del sistema</p>', unsafe_allow_html=True)
        chroma_ok = (Path(__file__).parent / "chroma_db").exists()
        modelo_ok = st.session_state.modelo_listo

        st.markdown(f"""
        <div class="status-badge">
            <div class="status-dot {'dot-green' if modelo_ok else 'dot-red'}"></div>
            <span>{'Modelo local cargado' if modelo_ok else 'Sin modelo descargado'}</span>
        </div>
        <div class="status-badge">
            <div class="status-dot {'dot-green' if chroma_ok else 'dot-red'}"></div>
            <span>{'ChromaDB local · 31,952 fragmentos' if chroma_ok else 'Base de datos no encontrada'}</span>
        </div>
        <div class="status-badge">
            <div class="status-dot dot-green"></div>
            <span>Sin tokens · Sin internet</span>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Selector de modelo
        st.markdown('<p class="sidebar-section-title">Modelo LLM Local</p>', unsafe_allow_html=True)

        descargados = listar_modelos_descargados()

        if descargados:
            opcion = st.selectbox(
                "Modelo en uso",
                options=descargados,
                index=descargados.index(st.session_state.modelo_local)
                      if st.session_state.modelo_local in descargados else 0,
                label_visibility="collapsed",
            )
            st.session_state.modelo_local = opcion
            info = MODELOS_DISPONIBLES[opcion]
            st.caption(f"📦 {info['filename']} · {info['tamano_gb']:.1f} GB")
        else:
            st.warning("No hay modelos descargados")

        # Boton para descargar modelo nuevo
        if st.button("⬇️ Descargar otro modelo", use_container_width=True):
            st.session_state.show_download = True

        if st.session_state.get("show_download"):
            st.markdown('<p class="sidebar-section-title">Modelos disponibles</p>', unsafe_allow_html=True)
            for nombre, info in MODELOS_DISPONIBLES.items():
                if nombre not in descargados:
                    if st.button(
                        f"⬇️ {nombre}\n{info['tamano_gb']:.1f} GB · RAM ≥{info['ram_min_gb']}GB",
                        key=f"dl_{nombre}",
                        use_container_width=True,
                    ):
                        st.session_state._descargar_modelo = nombre
                        st.rerun()

        st.divider()

        if st.button("＋ Nueva conversación", use_container_width=True):
            st.session_state.mensajes = []
            st.session_state.archivos = []
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
                    st.download_button(f"{icono} {p.name}", data=datos, file_name=p.name,
                                       mime=mime, use_container_width=True, key=f"sdl_{p.name}")

        st.divider()
        st.markdown(
            '<p style="font-size:0.7rem;color:#4a7090;padding:4px 0;">'
            'Ministerio de Obras Publicas · Chile<br>'
            'Modo: 100% local · Independiente</p>',
            unsafe_allow_html=True
        )


# ─────────────────────────────────────────────────────────────────────────────
# DESCARGA DE MODELO
# ─────────────────────────────────────────────────────────────────────────────
def _pantalla_descarga(nombre_modelo: str):
    # Defensivo: si el modelo ya no existe en el catalogo, limpia y vuelve al setup
    if nombre_modelo not in MODELOS_DISPONIBLES:
        if "_descargar_modelo" in st.session_state:
            del st.session_state._descargar_modelo
        st.rerun()
        return
    info = MODELOS_DISPONIBLES[nombre_modelo]
    st.markdown(f"""
    <div style='text-align:center; padding:2rem;'>
        <div style='font-size:3.5rem; margin-bottom:12px;'>⬇️</div>
        <h2 style='color:#064e3b;'>Descargando modelo</h2>
        <p style='color:#666; font-size:0.95rem;'>
            <b>{nombre_modelo}</b><br>
            {info['tamano_gb']:.1f} GB · Una sola vez<br>
            Despues funcionara 100% offline.
        </p>
    </div>
    """, unsafe_allow_html=True)

    progress = st.progress(0, text="Iniciando descarga...")

    try:
        descargar_modelo(nombre_modelo)
        progress.progress(100, text="Descarga completada")
        st.success("Modelo descargado correctamente. Recargando...")
        st.session_state.modelo_listo = True
        st.session_state.modelo_local = nombre_modelo
        if "_descargar_modelo" in st.session_state:
            del st.session_state._descargar_modelo
        if "show_download" in st.session_state:
            del st.session_state.show_download
        import time; time.sleep(2)
        st.rerun()
    except Exception as e:
        st.error(f"Error al descargar: {e}")
        if st.button("Reintentar"):
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# PANTALLA INICIAL — SIN MODELO
# ─────────────────────────────────────────────────────────────────────────────
def _pantalla_setup():
    st.markdown("""
    <div class="main-header">
        <div class="main-header-left">
            <div class="main-header-icon">🛣️</div>
            <div>
                <h1>Agente MOP — Configuración inicial</h1>
                <p>Modo Independiente · Selecciona tu modelo local</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="welcome-card">
        <h3>🌟 Bienvenido al Agente MOP Independiente</h3>
        <p>Para comenzar, descarga un modelo de IA local. Esto se hace UNA SOLA VEZ.
        Después el agente funcionará completamente offline, sin tokens, sin internet, sin costos.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Selecciona un modelo")
    st.caption("Elige según la potencia de tu PC. La descarga puede tardar varios minutos.")

    cols = st.columns(len(MODELOS_DISPONIBLES))
    for i, (nombre, info) in enumerate(MODELOS_DISPONIBLES.items()):
        with cols[i]:
            recomendado = "⭐ Recomendado" if nombre == MODELO_DEFAULT else ""
            st.markdown(f"""
            <div class="modelo-card">
                <h4>{nombre.split('(')[0].strip()}</h4>
                <p style='color:#047857;font-weight:600;'>{recomendado}</p>
                <p>📦 {info['tamano_gb']:.1f} GB</p>
                <p>🧠 RAM mínima: {info['ram_min_gb']} GB</p>
                <p style='font-size:0.75rem;color:#888;'>{info['filename']}</p>
            </div>
            """, unsafe_allow_html=True)

            if st.button(f"⬇️ Descargar este", key=f"setup_dl_{i}", use_container_width=True):
                st.session_state._descargar_modelo = nombre
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# CHAT
# ─────────────────────────────────────────────────────────────────────────────
def _md_a_html(texto: str) -> str:
    """Markdown basico a HTML."""
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


def _render_historial():
    for msg in st.session_state.mensajes:
        if msg["role"] == "user":
            st.markdown(f"""
            <div class="msg-user">
                <div class="msg-user-bubble">{msg["content"]}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="msg-agent">
                <div class="msg-agent-avatar">🤖</div>
                <div class="msg-agent-bubble">{_md_a_html(msg["content"])}</div>
            </div>""", unsafe_allow_html=True)


def _bienvenida():
    st.markdown("""
    <div class="msg-agent">
        <div class="msg-agent-avatar">🤖</div>
        <div class="msg-agent-bubble">
            <strong style="color:#064e3b;font-size:0.95rem;">¡Hola! Soy el Agente MOP Independiente.</strong>
            <p style="margin:8px 0 0;color:#444;">
                Funciono <strong>100% en tu PC</strong>, sin internet, sin tokens, sin costos.
                Tengo acceso a los <strong>9 volúmenes</strong> del Manual de Carreteras
                con <strong>31,952 fragmentos indexados</strong>.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="feature-card">
        <strong>⚡ Velocidad:</strong> Las primeras respuestas pueden tardar 30s
        (cargando modelo). Las siguientes son más rápidas.
    </div>
    <div class="feature-card">
        <strong>🔐 Privacidad total:</strong> Tus consultas nunca salen de tu PC.
    </div>
    <div class="feature-card">
        <strong>📋 Listados y reportes:</strong> Pídeme tablas en Excel o informes en Word.
    </div>
    """, unsafe_allow_html=True)


def _procesar(consulta: str):
    # Burbuja del usuario
    st.markdown(f"""
    <div class="msg-user">
        <div class="msg-user-bubble">{consulta}</div>
    </div>""", unsafe_allow_html=True)

    # Buscar contexto
    estado = st.empty()
    estado.info("🔍 Buscando en el Manual MOP...")

    try:
        fragmentos = buscar_contexto(consulta, n_resultados=8)
    except Exception:
        fragmentos = []

    estado.info(f"🤖 Generando respuesta con modelo local ({st.session_state.modelo_local})...")

    # Construir prompt
    historial_prev = st.session_state.mensajes[-4:]
    mensajes_api = construir_prompt_con_contexto(
        pregunta=consulta,
        fragmentos=fragmentos,
        historial=historial_prev,
    )

    # Streaming
    respuesta = ""
    contenedor = st.empty()
    try:
        for token in generar_streaming(
            mensajes=mensajes_api,
            nombre_modelo=st.session_state.modelo_local,
            max_tokens=2048,
            temperatura=0.3,
        ):
            respuesta += token
            contenedor.markdown(f"""
            <div class="msg-agent">
                <div class="msg-agent-avatar">🤖</div>
                <div class="msg-agent-bubble">{_md_a_html(respuesta)}<span style="opacity:.4">▌</span></div>
            </div>""", unsafe_allow_html=True)

        contenedor.markdown(f"""
        <div class="msg-agent">
            <div class="msg-agent-avatar">🤖</div>
            <div class="msg-agent-bubble">{_md_a_html(respuesta)}</div>
        </div>""", unsafe_allow_html=True)
        estado.empty()

    except Exception as e:
        estado.empty()
        contenedor.error(f"Error al generar respuesta: {e}")
        respuesta = "Error al generar respuesta."

    # Detectar si pide archivo
    solicitud = detectar_solicitud_archivo(consulta)
    archivos_nuevos = []

    if solicitud["excel"] or solicitud["word"]:
        col1, col2, _ = st.columns([1, 1, 3])
        if solicitud["excel"] and col1.button(
            "📊 Generar Excel", type="primary",
            key=f"gexcel_{len(st.session_state.mensajes)}",
        ):
            with st.spinner("Generando Excel desde la respuesta..."):
                try:
                    # Pedir al modelo local que extraiga JSON
                    json_prompt = [
                        {"role": "system", "content": "Devuelve SOLO un JSON valido (lista de dicts con campos consistentes), sin texto adicional."},
                        {"role": "user", "content": f"Extrae los datos tabulares de:\n{respuesta[:2500]}\n\nDevuelve un JSON tipo: [{{\"campo1\":\"...\",\"campo2\":\"...\"}}, ...]"},
                    ]
                    raw = "".join(generar_streaming(json_prompt, nombre_modelo=st.session_state.modelo_local, max_tokens=1500, temperatura=0.1))
                    m = re.search(r"\[.*\]", raw, re.DOTALL)
                    if m:
                        nombre = "_".join(consulta.split()[:4])
                        res = generar_excel(m.group(), nombre, titulo=consulta[:80])
                        if "correctamente:" in res:
                            p = Path(res.split("correctamente:")[-1].strip())
                            if p.exists():
                                archivos_nuevos.append(p)
                                st.session_state.archivos.append(str(p))
                except Exception as e:
                    st.warning(f"No se pudo generar Excel: {e}")

        if solicitud["word"] and col2.button(
            "📄 Generar Word",
            key=f"gword_{len(st.session_state.mensajes)}",
        ):
            with st.spinner("Generando Word..."):
                try:
                    nombre = "_".join(consulta.split()[:4])
                    res = generar_reporte(respuesta, nombre, titulo=consulta[:80])
                    if "correctamente:" in res:
                        p = Path(res.split("correctamente:")[-1].strip())
                        if p.exists():
                            archivos_nuevos.append(p)
                            st.session_state.archivos.append(str(p))
                except Exception as e:
                    st.warning(f"No se pudo generar Word: {e}")

    # Botones de descarga
    for p in archivos_nuevos:
        with open(p, "rb") as f: datos = f.read()
        icono = "📊" if p.suffix == ".xlsx" else "📄"
        mime = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                if p.suffix == ".xlsx" else
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        st.download_button(f"{icono} Descargar {p.name}", data=datos,
                           file_name=p.name, mime=mime,
                           key=f"dl_{p.name}_{len(st.session_state.mensajes)}")

    # Guardar historial
    st.session_state.mensajes.append({"role": "user", "content": consulta})
    st.session_state.mensajes.append({"role": "assistant", "content": respuesta})


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    _init()
    _sidebar()

    # ¿Hay descarga pendiente?
    if st.session_state.get("_descargar_modelo"):
        _pantalla_descarga(st.session_state._descargar_modelo)
        return

    # ¿Hay modelo descargado?
    if not listar_modelos_descargados():
        _pantalla_setup()
        return

    # Header
    st.markdown(f"""
    <div class="main-header">
        <div class="main-header-left">
            <div class="main-header-icon">🛣️</div>
            <div>
                <h1>Agente MOP — Modo Independiente</h1>
                <p>{st.session_state.modelo_local} · 100% local · Sin tokens</p>
            </div>
        </div>
        <div class="header-badge">● Offline · Sin costos</div>
    </div>
    """, unsafe_allow_html=True)

    # Bienvenida o historial
    if not st.session_state.mensajes:
        _bienvenida()
    else:
        _render_historial()

    # Input
    user_input = st.chat_input("Consulta el Manual de Carreteras...")
    if user_input:
        _procesar(user_input)
        st.rerun()


if __name__ == "__main__":
    main()
