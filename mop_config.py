from pathlib import Path

BASE_DIR = Path(__file__).parent
CHROMA_DIR = BASE_DIR / "chroma_db"
REPORTS_DIR = BASE_DIR / "reportes"
MANUALS_DIR = BASE_DIR / "manuales"

REPORTS_DIR.mkdir(exist_ok=True)

EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
TOP_K = 4  # bajamos de 5 a 4 para reducir memoria por consulta en Streamlit Cloud Free
COLLECTION_NAME = "mop_manual"

# Modelos Anthropic
MODELOS = {
    "Claude Opus 4.7  (mejor calidad)":  "claude-opus-4-7",
    "Claude Sonnet 4.6 (equilibrado)":   "claude-sonnet-4-6",
    "Claude Haiku 4.5  (mas rapido)":    "claude-haiku-4-5",
}
ANTHROPIC_MODEL = "claude-sonnet-4-6"

# Modelos Groq (gratis, muy rapidos)
MODELOS_GROQ = {
    "Llama 3.3 70B  (mejor calidad)":    "llama-3.3-70b-versatile",
    "Llama 3.1 8B   (mas rapido)":       "llama-3.1-8b-instant",
    "Mixtral 8x7B   (bueno en espanol)": "mixtral-8x7b-32768",
}
GROQ_MODEL_DEFAULT = "llama-3.3-70b-versatile"
