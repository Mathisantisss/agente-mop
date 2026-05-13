"""
Interfaz web del Agente MOP — Manual de Carreteras de Chile.
Modos: Groq (gratis, rapido) | Anthropic (nube) | Ollama (local, sin internet)
Inicio: streamlit run app.py
"""

import sys, os, re, json, time
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from mop_config import ANTHROPIC_MODEL, REPORTS_DIR, MODELOS, MODELOS_GROQ, GROQ_MODEL_DEFAULT
from agent import (
    TOOLS, SYSTEM_PROMPT, dispatch_tool,
    listar_volumenes, verificar_base_datos,
    generar_excel, generar_reporte,
)
from local_agent import buscar_contexto, construir_prompt_con_contexto, detectar_solicitud_archivo

# ---------------------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Agente MOP",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background-color: #f0f4f9; }
    .mop-header {
        background: linear-gradient(135deg, #1F497D 0%, #2E6DA4 100%);
        color: white; padding: 1.2rem 1.5rem; border-radius: 12px;
        margin-bottom: 1rem; box-shadow: 0 4px 12px rgba(31,73,125,0.25);
    }
    .mop-header h1 { margin: 0; font-size: 1.5rem; }
    .mop-header p  { margin: 0.3rem 0 0; font-size: 0.85rem; opacity: 0.9; }
    .badge-groq  { background:#e8f5e9; border-left:4px solid #4CAF50; padding:8px 12px; border-radius:6px; font-size:0.85rem; }
    .badge-cloud { background:#e3f2fd; border-left:4px solid #2196F3; padding:8px 12px; border-radius:6px; font-size:0.85rem; }
    .badge-local { background:#fff3e0; border-left:4px solid #FF9800; padding:8px 12px; border-radius:6px; font-size:0.85rem; }
    .vol-badge { display:inline-block; background:#DCE6F1; color:#1F497D;
        border-radius:6px; padding:2px 8px; font-size:0.78rem; font-weight:600; margin:2px; }
    [data-testid="stSidebar"] { background-color: #f8f9fa; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Estado de sesión
# ---------------------------------------------------------------------------
defaults = {
    "messages": [],
    "api_messages": [],
    "local_history": [],
    "archivos_generados": [],
    "modo": "groq",
    "groq_key_ok": False,
    "api_key_ok": False,
    "groq_modelo": GROQ_MODEL_DEFAULT,
    "modelo_activo": ANTHROPIC_MODEL,
    "ollama_modelo": "qwen2.5:7b",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Cargar claves guardadas
if not st.session_state.api_key_ok and os.environ.get("ANTHROPIC_API_KEY"):
    import anthropic
    st.session_state.anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    st.session_state.api_key_ok = True

if not st.session_state.groq_key_ok and os.environ.get("GROQ_API_KEY"):
    from groq import Groq
    st.session_state.groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
    st.session_state.groq_key_ok = True


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🛣️ Agente MOP")
    st.caption("Manual de Carreteras de Chile · Jun. 2025")
    st.divider()

    # ── Selector de modo ──────────────────────────────────────────────────
    st.markdown("### Motor de IA")
    modo = st.radio(
        "Motor",
        options=["⚡ Groq (gratis + rápido)", "☁️ Anthropic (nube)", "🖥️ Ollama (local)"],
        index=["groq", "nube", "local"].index(st.session_state.modo),
        label_visibility="collapsed",
    )
    if "Groq" in modo:
        st.session_state.modo = "groq"
    elif "Anthropic" in modo:
        st.session_state.modo = "nube"
    else:
        st.session_state.modo = "local"

    st.divider()

    # ── Config Groq ───────────────────────────────────────────────────────
    if st.session_state.modo == "groq":
        st.markdown('<div class="badge-groq">⚡ <b>Gratis · Sin límites · Muy rápido</b></div>', unsafe_allow_html=True)
        st.caption("")

        if not st.session_state.groq_key_ok:
            st.markdown("**🔑 API Key de Groq (gratis)**")
            st.caption("Obtén tu clave en [console.groq.com](https://console.groq.com/keys) — es gratis")
            key_input = st.text_input("Groq API Key", type="password",
                                       placeholder="gsk_...", label_visibility="collapsed")
            if st.button("Conectar Groq", type="primary", use_container_width=True):
                if key_input.startswith("gsk_"):
                    try:
                        from groq import Groq
                        client_test = Groq(api_key=key_input)
                        st.session_state.groq_client = client_test
                        st.session_state.groq_key_ok = True
                        # Guardar en .env
                        env_path = Path(__file__).parent / ".env"
                        lineas = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
                        lineas = [l for l in lineas if not l.startswith("GROQ_API_KEY")]
                        lineas.append(f"GROQ_API_KEY={key_input}")
                        env_path.write_text("\n".join(lineas) + "\n", encoding="utf-8")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.error("La clave debe comenzar con gsk_")
        else:
            st.success("Groq conectado", icon="⚡")
            sel_groq = st.selectbox("Modelo Groq", options=list(MODELOS_GROQ.keys()),
                                     label_visibility="visible")
            st.session_state.groq_modelo = MODELOS_GROQ[sel_groq]
            if st.button("Cambiar clave", use_container_width=True, key="change_groq"):
                st.session_state.groq_key_ok = False
                st.rerun()

    # ── Config Anthropic ──────────────────────────────────────────────────
    elif st.session_state.modo == "nube":
        st.markdown('<div class="badge-cloud">☁️ <b>API de Anthropic (pago)</b></div>', unsafe_allow_html=True)
        st.caption("")

        if not st.session_state.api_key_ok:
            st.markdown("**🔑 API Key de Anthropic**")
            key_input = st.text_input("Anthropic API Key", type="password",
                                       placeholder="sk-ant-...", label_visibility="collapsed")
            if st.button("Conectar", type="primary", use_container_width=True):
                if key_input.startswith("sk-ant-"):
                    try:
                        import anthropic
                        st.session_state.anthropic_client = anthropic.Anthropic(api_key=key_input)
                        st.session_state.api_key_ok = True
                        env_path = Path(__file__).parent / ".env"
                        lineas = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
                        lineas = [l for l in lineas if not l.startswith("ANTHROPIC_API_KEY")]
                        lineas.append(f"ANTHROPIC_API_KEY={key_input}")
                        env_path.write_text("\n".join(lineas) + "\n", encoding="utf-8")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.error("La clave debe comenzar con sk-ant-")
        else:
            st.success("Anthropic conectado", icon="✅")
            sel_claude = st.selectbox("Modelo", options=list(MODELOS.keys()),
                                       index=1, label_visibility="visible")
            st.session_state.modelo_activo = MODELOS[sel_claude]
            if st.button("Cambiar clave", use_container_width=True, key="change_ant"):
                st.session_state.api_key_ok = False
                st.rerun()

    # ── Config Ollama ─────────────────────────────────────────────────────
    else:
        st.markdown('<div class="badge-local">🖥️ <b>100% local · Sin internet</b></div>', unsafe_allow_html=True)
        st.caption("")

        modelos_ollama = {
            "qwen2.5:7b  (recomendado)": "qwen2.5:7b",
            "llama3.2:3b (más rápido)":  "llama3.2:3b",
            "mistral:7b":                 "mistral:7b",
        }
        sel_ol = st.selectbox("Modelo local", options=list(modelos_ollama.keys()),
                               label_visibility="visible")
        st.session_state.ollama_modelo = modelos_ollama[sel_ol]

        try:
            import ollama as ol
            ol.list()
            st.success("Ollama conectado", icon="🟢")
        except Exception:
            st.error("Ollama no está corriendo", icon="🔴")
            with st.expander("Cómo instalar"):
                st.markdown("1. Descarga en **[ollama.com](https://ollama.com)**\n"
                            "2. Instala y ábrelo\n3. En CMD ejecuta:\n```\nollama pull qwen2.5:7b\n```")

    st.divider()

    # ── Base de datos ─────────────────────────────────────────────────────
    n_frags = verificar_base_datos()
    if n_frags > 0:
        st.success(f"**Base de datos lista** · {n_frags:,} fragmentos", icon="✅")
        with st.expander("Ver volúmenes"):
            for linea in listar_volumenes().splitlines():
                if linea.startswith("- **"):
                    p = linea.replace("- **", "").split("**:")
                    if len(p) == 2:
                        st.markdown(f'<span class="vol-badge">{p[0].strip()}</span> {p[1].strip()}',
                                    unsafe_allow_html=True)
    else:
        st.error("Base vacía. Ejecuta: python ingest.py", icon="⚠️")

    st.divider()

    if st.button("🗑️ Nueva conversación", use_container_width=True):
        for k in ["messages", "api_messages", "local_history", "archivos_generados"]:
            st.session_state[k] = []
        st.rerun()

    # ── Archivos generados ────────────────────────────────────────────────
    if st.session_state.archivos_generados:
        st.divider()
        st.markdown("### 📁 Descargas")
        for ap in st.session_state.archivos_generados:
            p = Path(ap)
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
    st.markdown("### 💡 Ejemplos")
    for ej in ["¿Cuáles son los radios mínimos de curvatura?",
               "Crea un Excel con velocidades de diseño",
               "Genera un informe sobre señalización vial",
               "Diseño de pavimentos flexibles",
               "¿Qué dice el Vol. 3 sobre pendientes?"]:
        if st.button(ej, use_container_width=True, key=f"ej_{ej[:12]}"):
            st.session_state._ejemplo = ej
            st.rerun()
    st.caption("Agente MOP · Jun. 2025")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
modos_label = {
    "groq":  "⚡ Groq — Gratis y rápido",
    "nube":  "☁️ Anthropic API",
    "local": "🖥️ Ollama — 100% local",
}
st.markdown(f"""
<div class="mop-header">
    <h1>🛣️ Agente MOP — Manual de Carreteras de Chile</h1>
    <p>{modos_label[st.session_state.modo]} &nbsp;·&nbsp; {n_frags:,} fragmentos indexados &nbsp;·&nbsp; Ministerio de Obras Públicas · Jun. 2025</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Historial
# ---------------------------------------------------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="👤" if msg["role"] == "user" else "🛣️"):
        st.markdown(msg["content"])

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
ejemplo = getattr(st.session_state, "_ejemplo", None)
if ejemplo:
    del st.session_state._ejemplo

user_input = st.chat_input("Escribe tu consulta técnica sobre el Manual MOP...") or ejemplo
if not user_input:
    st.stop()

# Validar modo activo
if st.session_state.modo == "groq" and not st.session_state.groq_key_ok:
    st.info("👈 Ingresa tu API Key de Groq en el panel izquierdo (es gratis).", icon="⚡")
    st.stop()
if st.session_state.modo == "nube" and not st.session_state.api_key_ok:
    st.info("👈 Ingresa tu API Key de Anthropic en el panel izquierdo.", icon="🔑")
    st.stop()
if st.session_state.modo == "local":
    try:
        import ollama as ol; ol.list()
    except Exception:
        st.error("Ollama no está corriendo.", icon="🔴")
        st.stop()

with st.chat_message("user", avatar="👤"):
    st.markdown(user_input)
st.session_state.messages.append({"role": "user", "content": user_input})


# ============================================================
#  MODO GROQ
# ============================================================
def _descargas(archivos_nuevos):
    for p in archivos_nuevos:
        if p.exists():
            with open(p, "rb") as f:
                datos = f.read()
            icono = "📊" if p.suffix == ".xlsx" else "📄"
            mime = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    if p.suffix == ".xlsx" else
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            st.download_button(f"{icono} Descargar {p.name}", data=datos,
                               file_name=p.name, mime=mime,
                               key=f"dl_{p.name}_{len(st.session_state.messages)}")


def _guardar_archivo(resultado: str, archivos_nuevos: list):
    if "correctamente:" in resultado:
        try:
            p = Path(resultado.split("correctamente:")[-1].strip())
            if p.exists() and str(p) not in st.session_state.archivos_generados:
                archivos_nuevos.append(p)
                st.session_state.archivos_generados.append(str(p))
        except Exception:
            pass


if st.session_state.modo == "groq":
    from groq import Groq

    with st.chat_message("assistant", avatar="🛣️"):
        ph = st.empty()
        status_ph = st.empty()
        archivos_nuevos = []

        # 1. Buscar contexto en ChromaDB
        status_ph.info("🔍 Buscando en el Manual MOP...")
        fragmentos = buscar_contexto(user_input, n_resultados=5)

        # 2. Construir mensajes con contexto enriquecido
        mensajes = construir_prompt_con_contexto(
            pregunta=user_input,
            fragmentos=fragmentos,
            historial=st.session_state.local_history,
        )

        # 3. Llamar a Groq con streaming
        status_ph.empty()
        respuesta_completa = ""
        try:
            stream = st.session_state.groq_client.chat.completions.create(
                model=st.session_state.groq_modelo,
                messages=mensajes,
                stream=True,
                max_tokens=4096,
                temperature=0.3,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                respuesta_completa += delta
                ph.markdown(respuesta_completa + "▌")
            ph.markdown(respuesta_completa)

        except Exception as e:
            ph.error(f"Error de Groq: {e}")
            st.stop()

        # 4. Detectar si pide archivo
        solicitud = detectar_solicitud_archivo(user_input)
        if solicitud["excel"] or solicitud["word"]:
            st.divider()
            col1, col2 = st.columns(2)
            if solicitud["excel"] and col1.button("📊 Generar Excel", type="primary",
                                                    key="groq_excel"):
                with st.spinner("Generando Excel..."):
                    json_msgs = [
                        {"role": "system", "content": "Devuelve SOLO un JSON válido (lista de dicts), sin texto adicional ni bloques de código."},
                        {"role": "user", "content": f"Genera un JSON con datos tabulares para Excel basado en:\n{respuesta_completa[:2000]}\nConsulta: {user_input}"},
                    ]
                    jr = st.session_state.groq_client.chat.completions.create(
                        model="llama-3.1-8b-instant", messages=json_msgs, max_tokens=2000)
                    raw = jr.choices[0].message.content
                    m = re.search(r"\[.*\]", raw, re.DOTALL)
                    if m:
                        nombre = "_".join(user_input.split()[:4])
                        res = generar_excel(m.group(), nombre, titulo=user_input[:80])
                        _guardar_archivo(res, archivos_nuevos)
                        st.success("Excel generado")
                    else:
                        st.warning("No pude extraer datos estructurados.")

            if solicitud["word"] and col2.button("📄 Generar Word", key="groq_word"):
                with st.spinner("Generando Word..."):
                    nombre = "_".join(user_input.split()[:4])
                    res = generar_reporte(respuesta_completa, nombre, titulo=user_input[:80])
                    _guardar_archivo(res, archivos_nuevos)
                    st.success("Word generado")

        _descargas(archivos_nuevos)

    st.session_state.local_history.append({"role": "user", "content": user_input})
    st.session_state.local_history.append({"role": "assistant", "content": respuesta_completa})
    st.session_state.messages.append({"role": "assistant", "content": respuesta_completa})


# ============================================================
#  MODO ANTHROPIC
# ============================================================
elif st.session_state.modo == "nube":
    import anthropic as ant

    with st.chat_message("assistant", avatar="🛣️"):
        ph = st.empty()
        status_ph = st.empty()
        full_response = ""
        archivos_nuevos = []
        modelo = st.session_state.get("modelo_activo", ANTHROPIC_MODEL)
        st.session_state.api_messages.append({"role": "user", "content": user_input})

        def llamar_api(msgs, intento=1):
            try:
                return st.session_state.anthropic_client.messages.create(
                    model=modelo, max_tokens=4096, system=SYSTEM_PROMPT,
                    tools=TOOLS, messages=msgs,
                )
            except ant.RateLimitError:
                if intento <= 3:
                    espera = 20 * intento
                    status_ph.warning(f"⏳ Límite de velocidad. Reintentando en {espera}s...\n\n"
                                      "💡 Cambia a **Groq** (gratis y más rápido).")
                    time.sleep(espera)
                    return llamar_api(msgs, intento + 1)
                raise

        with st.spinner("Consultando el Manual MOP..."):
            while True:
                response = llamar_api(st.session_state.api_messages)
                text_blocks, tool_uses = [], []
                for block in response.content:
                    if block.type == "text":   text_blocks.append(block.text)
                    elif block.type == "tool_use": tool_uses.append(block)

                st.session_state.api_messages.append({"role": "assistant", "content": response.content})

                if text_blocks:
                    full_response = "\n".join(text_blocks)
                    ph.markdown(full_response)

                if response.stop_reason == "end_turn" or not tool_uses:
                    break

                tool_results = []
                for tb in tool_uses:
                    iconos = {"buscar_en_manual": "🔍 Buscando...", "generar_excel": "📊 Generando Excel...",
                              "generar_reporte": "📄 Generando Word...", "listar_volumenes": "📚 Listando..."}
                    status_ph.info(iconos.get(tb.name, f"⚙️ {tb.name}..."))
                    resultado = dispatch_tool(tb.name, tb.input)
                    _guardar_archivo(resultado, archivos_nuevos)
                    tool_results.append({"type": "tool_result", "tool_use_id": tb.id, "content": resultado})

                status_ph.empty()
                st.session_state.api_messages.append({"role": "user", "content": tool_results})

        status_ph.empty()
        ph.markdown(full_response)
        _descargas(archivos_nuevos)

    st.session_state.messages.append({"role": "assistant", "content": full_response})


# ============================================================
#  MODO OLLAMA
# ============================================================
else:
    import ollama as ol

    with st.chat_message("assistant", avatar="🛣️"):
        ph = st.empty()
        status_ph = st.empty()
        archivos_nuevos = []

        status_ph.info("🔍 Buscando en el Manual MOP...")
        fragmentos = buscar_contexto(user_input, n_resultados=5)
        mensajes = construir_prompt_con_contexto(user_input, fragmentos, st.session_state.local_history)

        status_ph.empty()
        respuesta_completa = ""
        try:
            stream = ol.chat(model=st.session_state.ollama_modelo, messages=mensajes, stream=True)
            for chunk in stream:
                respuesta_completa += chunk["message"]["content"]
                ph.markdown(respuesta_completa + "▌")
            ph.markdown(respuesta_completa)
        except ol.ResponseError as e:
            modelo = st.session_state.ollama_modelo
            ph.error(f"Modelo **{modelo}** no descargado.\n\nEjecuta en CMD:\n```\nollama pull {modelo}\n```")
            st.stop()

        solicitud = detectar_solicitud_archivo(user_input)
        if solicitud["excel"] or solicitud["word"]:
            st.divider()
            col1, col2 = st.columns(2)
            if solicitud["excel"] and col1.button("📊 Generar Excel", type="primary", key="ol_excel"):
                with st.spinner("Generando..."):
                    json_msgs = [
                        {"role": "system", "content": "Devuelve SOLO JSON (lista de dicts), sin texto extra."},
                        {"role": "user", "content": f"JSON para Excel de:\n{respuesta_completa[:2000]}"},
                    ]
                    jr = ol.chat(model=st.session_state.ollama_modelo, messages=json_msgs)
                    m = re.search(r"\[.*\]", jr["message"]["content"], re.DOTALL)
                    if m:
                        res = generar_excel(m.group(), "_".join(user_input.split()[:4]), titulo=user_input[:80])
                        _guardar_archivo(res, archivos_nuevos)
                        st.success("Excel generado")

            if solicitud["word"] and col2.button("📄 Generar Word", key="ol_word"):
                with st.spinner("Generando..."):
                    res = generar_reporte(respuesta_completa, "_".join(user_input.split()[:4]), titulo=user_input[:80])
                    _guardar_archivo(res, archivos_nuevos)
                    st.success("Word generado")

        _descargas(archivos_nuevos)

    st.session_state.local_history.append({"role": "user", "content": user_input})
    st.session_state.local_history.append({"role": "assistant", "content": respuesta_completa})
    st.session_state.messages.append({"role": "assistant", "content": respuesta_completa})
