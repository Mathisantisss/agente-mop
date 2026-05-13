"""
Agente RAG 100% INDEPENDIENTE.
- Sin tokens, sin internet, sin APIs externas.
- Modelo LLM corre localmente via GPT4All (binarios precompilados, sin compilar).
- Embeddings: sentence-transformers (local).
- Vector store: ChromaDB (local).

Modelos recomendados (descarga automatica primera vez):
  - Llama-3.2-3B-Instruct-Q4_0      (~1.9 GB) — rapido, buen español
  - Qwen2.5-7B-Instruct              (~4.6 GB) — mejor calidad, español tecnico
  - Phi-3.5-mini-instruct            (~2.2 GB) — equilibrado
"""

from pathlib import Path
from typing import Optional

# Directorio para los modelos descargados (persistente)
MODEL_DIR = Path(__file__).parent / "modelos_locales"
MODEL_DIR.mkdir(exist_ok=True)

# Catalogo de modelos disponibles (verificados en el registry de GPT4All)
MODELOS_DISPONIBLES = {
    "Llama 3.2 3B (rapido, recomendado)": {
        "filename": "Llama-3.2-3B-Instruct-Q4_0.gguf",
        "tamano_gb": 1.9,
        "ram_min_gb": 4,
        "descripcion": "Rapido, buen español, ideal para empezar",
    },
    "Llama 3.2 1B (super rapido)": {
        "filename": "Llama-3.2-1B-Instruct-Q4_0.gguf",
        "tamano_gb": 0.8,
        "ram_min_gb": 2,
        "descripcion": "Mas pequeño, respuestas en segundos",
    },
    "Llama 3.1 8B (mejor calidad)": {
        "filename": "Meta-Llama-3.1-8B-Instruct-128k-Q4_0.gguf",
        "tamano_gb": 4.7,
        "ram_min_gb": 8,
        "descripcion": "Mejor calidad, mas lento, contexto 128k",
    },
    "Mistral 7B (técnico)": {
        "filename": "mistral-7b-instruct-v0.1.Q4_0.gguf",
        "tamano_gb": 4.1,
        "ram_min_gb": 8,
        "descripcion": "Bueno para texto tecnico",
    },
    "Qwen 2.5 Coder 7B (técnico)": {
        "filename": "qwen2.5-coder-7b-instruct-q4_0.gguf",
        "tamano_gb": 4.4,
        "ram_min_gb": 8,
        "descripcion": "Excelente para contenido tecnico/codigo",
    },
}

MODELO_DEFAULT = "Llama 3.2 3B (rapido, recomendado)"

# Cache global del modelo cargado
_modelo_cargado = None
_nombre_modelo_cargado = None


def listar_modelos_descargados() -> list[str]:
    """Retorna los nombres de modelos ya descargados localmente."""
    descargados = []
    for nombre, info in MODELOS_DISPONIBLES.items():
        if (MODEL_DIR / info["filename"]).exists():
            descargados.append(nombre)
    return descargados


def descargar_modelo(nombre: str, callback_progreso=None) -> Path:
    """
    Descarga un modelo del catalogo si no existe localmente.
    Usa el mecanismo built-in de GPT4All que descarga desde su CDN oficial.
    Retorna la ruta al archivo .gguf.
    """
    if nombre not in MODELOS_DISPONIBLES:
        raise ValueError(f"Modelo desconocido: {nombre}")

    info = MODELOS_DISPONIBLES[nombre]
    ruta = MODEL_DIR / info["filename"]

    if ruta.exists():
        return ruta

    from gpt4all import GPT4All

    if callback_progreso:
        callback_progreso(f"Descargando {nombre} ({info['tamano_gb']:.1f} GB)...")

    # Instanciar el modelo lo descarga automaticamente del registry oficial
    modelo = GPT4All(
        model_name=info["filename"],
        model_path=str(MODEL_DIR),
        allow_download=True,
        verbose=False,
    )
    # No queremos cargarlo ahora, solo descargarlo
    try:
        modelo.close()
    except Exception:
        pass

    if not ruta.exists():
        raise FileNotFoundError(
            f"La descarga del modelo {info['filename']} no completo correctamente"
        )

    return ruta


def cargar_modelo(nombre: str = MODELO_DEFAULT, n_threads: Optional[int] = None):
    """
    Carga el modelo en memoria (con cache).
    Si ya hay otro modelo cargado, lo libera primero.
    """
    global _modelo_cargado, _nombre_modelo_cargado

    if _modelo_cargado is not None and _nombre_modelo_cargado == nombre:
        return _modelo_cargado

    # Liberar modelo anterior
    if _modelo_cargado is not None:
        try:
            _modelo_cargado.close()
        except Exception:
            pass
        _modelo_cargado = None

    if nombre not in MODELOS_DISPONIBLES:
        raise ValueError(f"Modelo desconocido: {nombre}")

    info = MODELOS_DISPONIBLES[nombre]
    ruta = MODEL_DIR / info["filename"]

    # Asegurar descarga
    if not ruta.exists():
        descargar_modelo(nombre)

    from gpt4all import GPT4All

    # Intentar GPU (Vulkan/CUDA) primero, fallback a CPU si falla
    # GPT4All auto-detecta: "gpu" usa Vulkan en cualquier GPU, incluyendo RTX
    try:
        _modelo_cargado = GPT4All(
            model_name=info["filename"],
            model_path=str(MODEL_DIR),
            allow_download=False,
            device="gpu",           # usa Vulkan (RTX, AMD, Intel)
            n_threads=n_threads,
            verbose=False,
        )
    except Exception as e:
        print(f"[INFO] GPU no disponible, usando CPU: {e}")
        _modelo_cargado = GPT4All(
            model_name=info["filename"],
            model_path=str(MODEL_DIR),
            allow_download=False,
            device="cpu",
            n_threads=n_threads,
            verbose=False,
        )
    _nombre_modelo_cargado = nombre
    return _modelo_cargado


# ─────────────────────────────────────────────────────────────────────────────
# GENERACION CON STREAMING
# ─────────────────────────────────────────────────────────────────────────────
def generar_streaming(
    mensajes: list[dict],
    nombre_modelo: str = MODELO_DEFAULT,
    max_tokens: int = 2048,
    temperatura: float = 0.3,
):
    """
    Generador que produce tokens uno a uno (compatible con streaming en Streamlit).

    Args:
        mensajes: lista de dicts {role, content} estilo OpenAI
        nombre_modelo: nombre del modelo del catalogo
        max_tokens: maximo de tokens a generar
        temperatura: 0.0 = deterministico, 1.0 = creativo

    Yields:
        Strings (tokens) generados en secuencia.
    """
    modelo = cargar_modelo(nombre_modelo)

    # Convertir mensajes al formato de prompt que entiende el modelo
    # GPT4All soporta chat_session que mantiene contexto
    sistema = ""
    historial_chat = []

    for msg in mensajes:
        if msg["role"] == "system":
            sistema = msg["content"]
        elif msg["role"] == "user":
            historial_chat.append(("user", msg["content"]))
        elif msg["role"] == "assistant":
            historial_chat.append(("assistant", msg["content"]))

    # Construir prompt en formato simple
    prompt = ""
    if sistema:
        prompt += f"### Instrucciones\n{sistema}\n\n"

    for role, content in historial_chat[:-1]:  # historial previo
        if role == "user":
            prompt += f"### Usuario\n{content}\n\n"
        else:
            prompt += f"### Asistente\n{content}\n\n"

    # Ultimo mensaje (la consulta actual)
    if historial_chat and historial_chat[-1][0] == "user":
        prompt += f"### Usuario\n{historial_chat[-1][1]}\n\n### Asistente\n"

    # Generar con streaming
    with modelo.chat_session(system_prompt=sistema):
        ultimo_user = historial_chat[-1][1] if historial_chat else ""

        for token in modelo.generate(
            ultimo_user,
            max_tokens=max_tokens,
            temp=temperatura,
            top_k=40,
            top_p=0.9,
            streaming=True,
        ):
            yield token


def generar_completo(
    mensajes: list[dict],
    nombre_modelo: str = MODELO_DEFAULT,
    max_tokens: int = 2048,
    temperatura: float = 0.3,
) -> str:
    """Version no-streaming: retorna la respuesta completa."""
    return "".join(generar_streaming(mensajes, nombre_modelo, max_tokens, temperatura))


# ─────────────────────────────────────────────────────────────────────────────
# UTILIDAD: Verificacion de estado
# ─────────────────────────────────────────────────────────────────────────────
def estado_sistema() -> dict:
    """Retorna info del estado del LLM local."""
    descargados = listar_modelos_descargados()
    return {
        "modelos_descargados": descargados,
        "modelos_disponibles": list(MODELOS_DISPONIBLES.keys()),
        "modelo_cargado": _nombre_modelo_cargado,
        "directorio": str(MODEL_DIR),
    }
