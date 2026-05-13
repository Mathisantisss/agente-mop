"""
config.py — Re-export desde mop_config para compatibilidad.

Este archivo existe solo como shim: si algo importa de `config`,
recibe todo lo que define `mop_config`. Esto evita romper código
legado y a la vez nos protege de conflictos de nombres con módulos
internos de chromadb / streamlit (que tienen su propio `config`).
"""
from mop_config import *  # noqa: F401,F403
from mop_config import (  # noqa: F401
    BASE_DIR,
    CHROMA_DIR,
    REPORTS_DIR,
    MANUALS_DIR,
    EMBEDDING_MODEL,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    TOP_K,
    COLLECTION_NAME,
    MODELOS,
    ANTHROPIC_MODEL,
    MODELOS_GROQ,
    GROQ_MODEL_DEFAULT,
)
