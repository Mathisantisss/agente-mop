"""
custom_embeddings.py

Función de embeddings basada en fastembed (ONNX) en lugar de
sentence-transformers (PyTorch). Misma calidad de vectores con
~5x menos memoria — crítico para Streamlit Cloud Free Tier (1 GB).

Usa el mismo modelo subyacente (paraphrase-multilingual-MiniLM-L12-v2)
que se usó para indexar la base ChromaDB, así que los vectores son
compatibles sin re-vectorizar.
"""

from __future__ import annotations

from typing import List, Optional

# fastembed solo carga el modelo en el primer uso (lazy)
_model = None
_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _get_model():
    """Carga lazy del modelo de embeddings (singleton)."""
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        # threads=2 para no saturar el CPU compartido de Streamlit Cloud
        _model = TextEmbedding(model_name=_MODEL_NAME, threads=2)
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Genera embeddings para una lista de textos."""
    if not texts:
        return []
    model = _get_model()
    return [vec.tolist() for vec in model.embed(texts)]


class FastEmbedFunction:
    """
    Función de embeddings compatible con la API que ChromaDB espera.
    Se hace pasar por "sentence_transformer" para que ChromaDB no se
    queje de mismatch con la function que se usó al indexar.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or _MODEL_NAME

    def __call__(self, input: List[str]) -> List[List[float]]:
        # ChromaDB >= 0.5 pasa el argumento como 'input'
        return embed_texts(input)

    # ─── Métodos que ChromaDB >= 1.x espera explícitamente ───
    def embed_query(self, input: List[str]) -> List[List[float]]:
        """ChromaDB llama este metodo al hacer query()."""
        return embed_texts(input)

    def embed_documents(self, input: List[str]) -> List[List[float]]:
        """ChromaDB llama este metodo al hacer add()."""
        return embed_texts(input)

    # ─── Identificadores que ChromaDB usa para validar compatibilidad ───
    @staticmethod
    def name() -> str:
        # IMPORTANTE: este nombre debe coincidir con el de la función
        # que se usó para indexar la base (SentenceTransformerEmbeddingFunction
        # se identifica como "sentence_transformer"), si no ChromaDB se queja.
        return "sentence_transformer"

    @staticmethod
    def default_space() -> str:
        return "cosine"

    @staticmethod
    def supported_spaces() -> List[str]:
        return ["cosine", "l2", "ip"]

    # Métodos requeridos por chromadb >= 1.x
    def get_config(self) -> dict:
        return {"model_name": self.model_name}

    @classmethod
    def build_from_config(cls, config: dict) -> "FastEmbedFunction":
        return cls(model_name=config.get("model_name"))

    @staticmethod
    def is_legacy() -> bool:
        # Para que ChromaDB no aplique validaciones estrictas legacy
        return False
