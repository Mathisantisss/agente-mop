"""
migrate_to_pinecone.py
Migra todos los vectores y metadatos de ChromaDB local a Pinecone.
"""

import os
import sys
import time

# Cargar .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- Configuracion ---
INDEX_NAME = "mop-manual"
DIMENSION = 384
METRIC = "cosine"
BATCH_SIZE = 100

# Leer configuracion del proyecto
try:
    from config import COLLECTION_NAME, CHROMA_PATH
except ImportError:
    COLLECTION_NAME = "mop_manual"
    CHROMA_PATH = "./chroma_db"


def get_pinecone_api_key():
    key = os.environ.get("PINECONE_API_KEY", "")
    if not key:
        print("ERROR: No se encontro PINECONE_API_KEY en el entorno ni en .env")
        sys.exit(1)
    return key


def conectar_chroma():
    try:
        import chromadb
    except ImportError:
        print("ERROR: chromadb no esta instalado. Ejecuta: pip install chromadb")
        sys.exit(1)

    print(f"Conectando a ChromaDB local en: {CHROMA_PATH}")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(name=COLLECTION_NAME)
    total = collection.count()
    print(f"Coleccion '{COLLECTION_NAME}': {total} fragmentos encontrados.")
    return collection, total


def conectar_pinecone(api_key):
    try:
        from pinecone import Pinecone, ServerlessSpec
    except ImportError:
        print("ERROR: pinecone-client no esta instalado. Ejecuta: pip install pinecone-client>=3.0.0")
        sys.exit(1)

    print("Conectando a Pinecone...")
    pc = Pinecone(api_key=api_key)

    existing_indexes = [idx.name for idx in pc.list_indexes()]

    if INDEX_NAME not in existing_indexes:
        print(f"Creando index '{INDEX_NAME}' (dimension={DIMENSION}, metric={METRIC})...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=DIMENSION,
            metric=METRIC,
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        # Esperar a que el index este listo
        while not pc.describe_index(INDEX_NAME).status["ready"]:
            print("  Esperando que el index este listo...")
            time.sleep(2)
        print(f"Index '{INDEX_NAME}' creado exitosamente.")
    else:
        print(f"El index '{INDEX_NAME}' ya existe.")

    index = pc.Index(INDEX_NAME)
    stats = index.describe_index_stats()
    count_actual = stats.get("total_vector_count", 0)

    if count_actual > 0:
        print(f"\nATENCION: El index ya contiene {count_actual} vectores.")
        respuesta = input("¿Deseas continuar y agregar mas vectores? (s/n): ").strip().lower()
        if respuesta not in ("s", "si", "y", "yes"):
            print("Migracion cancelada por el usuario.")
            sys.exit(0)

    return index


def migrar(collection, total, pinecone_index):
    print(f"\nIniciando migracion de {total} vectores en batches de {BATCH_SIZE}...")
    offset = 0
    total_subidos = 0

    while offset < total:
        # Obtener batch de ChromaDB
        resultado = collection.get(
            limit=BATCH_SIZE,
            offset=offset,
            include=["embeddings", "metadatas", "documents"],
        )

        ids = resultado["ids"]
        embeddings = resultado["embeddings"]
        metadatas = resultado["metadatas"]
        documents = resultado["documents"]

        if not ids:
            break

        # Construir vectores para Pinecone
        vectores = []
        for i, vec_id in enumerate(ids):
            meta = metadatas[i] if metadatas else {}
            # Incluir el texto del fragmento en los metadatos de Pinecone
            meta["texto"] = documents[i] if documents else ""
            vectores.append({
                "id": vec_id,
                "values": embeddings[i],
                "metadata": meta,
            })

        pinecone_index.upsert(vectors=vectores)
        total_subidos += len(vectores)
        offset += BATCH_SIZE

        porcentaje = (total_subidos / total) * 100
        print(f"  Subidos {total_subidos}/{total} ({porcentaje:.1f}%)...")

    return total_subidos


def main():
    print("=" * 60)
    print("  MIGRACION ChromaDB -> Pinecone: Manual de Carreteras MOP")
    print("=" * 60)

    api_key = get_pinecone_api_key()
    collection, total = conectar_chroma()
    pinecone_index = conectar_pinecone(api_key)

    inicio = time.time()
    total_subidos = migrar(collection, total, pinecone_index)
    duracion = time.time() - inicio

    print("\n" + "=" * 60)
    print(f"  Migracion completada en {duracion:.1f} segundos.")
    print(f"  Total de vectores subidos a Pinecone: {total_subidos}")
    print("=" * 60)


if __name__ == "__main__":
    main()
