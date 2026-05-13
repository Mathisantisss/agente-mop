"""
Ingesta de PDFs del Manual de Carreteras MOP hacia ChromaDB.
Ejecutar una sola vez (o cuando se agreguen nuevos volúmenes):
    python ingest.py

Usa pypdfium2 para extraccion de texto (memoria eficiente con PDFs grandes).
"""

import gc
import re
import sys
from pathlib import Path

import chromadb
import pypdfium2 as pdfium
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CHROMA_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    MANUALS_DIR,
)


def log(msg: str) -> None:
    """Print simple sin caracteres especiales para compatibilidad Windows."""
    print(msg, flush=True)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Divide texto en trozos con overlap, respetando limites de oracion."""
    if not text.strip():
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        if end < text_len:
            boundary = text.rfind(". ", start, end)
            if boundary != -1 and boundary > start + chunk_size // 2:
                end = boundary + 1

        chunk = text[start:end].strip()
        if len(chunk) > 50:  # descartar fragmentos muy cortos
            chunks.append(chunk)

        start = end - overlap if end < text_len else text_len

    return chunks


def extract_text_from_pdf(pdf_path: Path) -> list[dict]:
    """
    Extrae texto pagina a pagina usando pypdfium2.
    Acumula texto en ventanas de 5 paginas antes de chunkear.
    """
    chunks_with_meta = []

    try:
        doc = pdfium.PdfDocument(str(pdf_path))
    except Exception as e:
        log(f"  [ERROR] No se pudo abrir {pdf_path.name}: {e}")
        return []

    total_pages = len(doc)
    log(f"  -> {total_pages} paginas detectadas")

    window_text = ""
    window_start = 1
    WINDOW = 5  # paginas por ventana de chunking

    for page_num in range(total_pages):
        try:
            page = doc[page_num]
            textpage = page.get_textpage()
            page_text = textpage.get_text_range()
            textpage.close()
            page.close()

            if page_text:
                window_text += " " + page_text.replace("\r", " ").replace("\n", " ")

        except Exception as e:
            log(f"  [AVISO] Pagina {page_num + 1} omitida: {e}")
            page_text = ""

        # Chunkear cada WINDOW paginas o al final
        real_page = page_num + 1
        if real_page % WINDOW == 0 or real_page == total_pages:
            if window_text.strip():
                for chunk in chunk_text(window_text.strip()):
                    chunks_with_meta.append({
                        "text": chunk,
                        "page_start": window_start,
                        "page_end": real_page,
                    })
            window_text = ""
            window_start = real_page + 1

        # Liberar memoria cada 50 paginas
        if real_page % 50 == 0:
            gc.collect()
            log(f"  -> Pagina {real_page}/{total_pages} procesada...")

    doc.close()
    gc.collect()
    return chunks_with_meta


def detect_volume(filename: str) -> str:
    """Extrae numero de volumen del nombre de archivo."""
    filename_lower = filename.lower()

    patterns = [
        r"volumen[_\s\-]*(\d+)",
        r"vol(?:umen)?[_\s\-]*(\d+)",
        r"v(\d+)[_\s\-]",
        r"tomo[_\s\-]*(\d+)",
        r"(\d+)[_\s\-]",
    ]

    for pattern in patterns:
        match = re.search(pattern, filename_lower)
        if match:
            return f"Volumen {match.group(1)}"

    return f"Sin clasificar ({filename})"


def ingest_pdfs(pdfs_dir: Path = MANUALS_DIR) -> None:
    pdf_files = sorted(pdfs_dir.glob("*.pdf"))

    if not pdf_files:
        log(f"No se encontraron PDFs en: {pdfs_dir}")
        log("Coloca los PDFs del Manual MOP en esa carpeta y vuelve a ejecutar.")
        sys.exit(0)

    log(f"\n=== Ingesta de {len(pdf_files)} PDF(s) ===\n")

    log("Cargando modelo de embeddings (puede tardar la primera vez)...")
    embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    log("Modelo cargado.\n")

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

    existing_ids = set(collection.get(include=[])["ids"])
    log(f"Fragmentos existentes en la base: {len(existing_ids)}\n")

    total_nuevos = 0

    for idx, pdf_path in enumerate(pdf_files, 1):
        volume = detect_volume(pdf_path.name)
        size_mb = pdf_path.stat().st_size / (1024 * 1024)
        log(f"[{idx}/{len(pdf_files)}] Procesando: {volume} — {pdf_path.name} ({size_mb:.1f} MB)")

        try:
            chunks = extract_text_from_pdf(pdf_path)
            log(f"  -> {len(chunks)} fragmentos extraidos")

            if not chunks:
                log(f"  [AVISO] No se extrajo texto de {pdf_path.name}")
                continue

            BATCH_SIZE = 50  # lotes pequeños para PDFs grandes
            batch_ids, batch_docs, batch_metas = [], [], []
            nuevos = 0

            for i, chunk in enumerate(chunks):
                chunk_id = f"{pdf_path.stem}_p{chunk['page_start']}-{chunk['page_end']}_c{i}"

                if chunk_id in existing_ids:
                    continue

                batch_ids.append(chunk_id)
                batch_docs.append(chunk["text"])
                batch_metas.append({
                    "volumen": volume,
                    "archivo": pdf_path.name,
                    "pagina_inicio": chunk["page_start"],
                    "pagina_fin": chunk["page_end"],
                })
                nuevos += 1

                if len(batch_ids) >= BATCH_SIZE:
                    collection.add(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
                    log(f"  -> Batch guardado ({nuevos} fragmentos hasta ahora)...")
                    batch_ids, batch_docs, batch_metas = [], [], []
                    gc.collect()

            if batch_ids:
                collection.add(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)

            total_nuevos += nuevos
            log(f"  [OK] {volume}: {nuevos} fragmentos nuevos agregados.\n")

        except Exception as e:
            log(f"  [ERROR] Fallo en {pdf_path.name}: {e}\n")

        gc.collect()

    total = collection.count()
    log(f"\n=== Ingesta completada ===")
    log(f"Fragmentos nuevos esta sesion : {total_nuevos}")
    log(f"Total en la base de datos     : {total}\n")


if __name__ == "__main__":
    ingest_pdfs()
