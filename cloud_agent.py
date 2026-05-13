"""
cloud_agent.py
Modulo de busqueda semantica usando Pinecone como vector store en la nube.
Reemplaza a local_agent.py cuando ChromaDB no esta disponible.
"""

import os

# Cargar .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuracion del proyecto
try:
    from config import EMBEDDING_MODEL, COLLECTION_NAME, TOP_K
except ImportError:
    EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
    COLLECTION_NAME = "mop_manual"
    TOP_K = 5

INDEX_NAME = "mop-manual"

# Cache del modelo de embeddings para no cargarlo multiples veces
_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


def _get_pinecone_index():
    """Retorna el index de Pinecone o None si hay algun error."""
    api_key = os.environ.get("PINECONE_API_KEY", "")
    if not api_key:
        # Intentar leer desde Streamlit secrets si estamos en ese entorno
        try:
            import streamlit as st
            api_key = st.secrets.get("PINECONE_API_KEY", "")
        except Exception:
            pass

    if not api_key:
        return None

    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=api_key)
        return pc.Index(INDEX_NAME)
    except Exception:
        return None


def buscar_en_pinecone(consulta: str, volumen: str = "", n_resultados: int = TOP_K) -> list:
    """
    Busca fragmentos relevantes en Pinecone para la consulta dada.

    Args:
        consulta: Texto de la pregunta o busqueda.
        volumen: Filtro opcional por volumen del manual (ej. "Volumen 3").
        n_resultados: Cantidad de resultados a retornar.

    Returns:
        Lista de dicts con claves: texto, volumen, pag_inicio, pag_fin, relevancia.
        Retorna [] si falla la conexion o no hay resultados.
    """
    if not consulta or not consulta.strip():
        return []

    try:
        modelo = _get_embedding_model()
        embedding = modelo.encode(consulta).tolist()
    except Exception as e:
        print(f"[cloud_agent] Error al generar embedding: {e}")
        return []

    index = _get_pinecone_index()
    if index is None:
        print("[cloud_agent] No se pudo conectar a Pinecone (verifica PINECONE_API_KEY).")
        return []

    try:
        # Construir filtro de metadatos si se especifico un volumen
        filtro = None
        if volumen and volumen.strip():
            filtro = {"volumen": {"$eq": volumen.strip()}}

        respuesta = index.query(
            vector=embedding,
            top_k=n_resultados,
            include_metadata=True,
            filter=filtro,
        )

        resultados = []
        for match in respuesta.get("matches", []):
            meta = match.get("metadata", {})
            resultados.append({
                "texto": meta.get("texto", ""),
                "volumen": meta.get("volumen", ""),
                "pag_inicio": meta.get("pag_inicio", None),
                "pag_fin": meta.get("pag_fin", None),
                "relevancia": round(float(match.get("score", 0.0)), 4),
            })

        return resultados

    except Exception as e:
        print(f"[cloud_agent] Error al consultar Pinecone: {e}")
        return []


def verificar_pinecone() -> int:
    """
    Verifica la conexion con Pinecone y retorna el numero de vectores indexados.

    Returns:
        Numero de vectores en el index, o 0 si no hay conexion o hay un error.
    """
    index = _get_pinecone_index()
    if index is None:
        return 0

    try:
        stats = index.describe_index_stats()
        return int(stats.get("total_vector_count", 0))
    except Exception:
        return 0
