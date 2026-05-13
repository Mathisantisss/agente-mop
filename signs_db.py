"""
Base de datos estructurada de señales del Manual MOP.

A diferencia del RAG semantico, este modulo extrae los codigos de senales
mediante REGEX deterministico recorriendo TODOS los fragmentos. Asi se
garantiza precision total: cada codigo encontrado en el manual aparece aqui.
"""

import re
import json
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from config import CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL

CACHE_FILE = Path(__file__).parent / "signs_cache.json"

# ─────────────────────────────────────────────────────────────────────────────
# CATALOGO DE TIPOS DE SEÑALES MOP (segun nomenclatura oficial)
# ─────────────────────────────────────────────────────────────────────────────
TIPOS_SEÑALES = {
    # Reglamentarias
    "R":   "Reglamentaria (general)",
    "RP":  "Reglamentaria de Prioridad",
    "RPO": "Reglamentaria de Prohibicion",
    "RR":  "Reglamentaria de Restriccion",
    "RM":  "Reglamentaria de Movimiento",
    "RE":  "Reglamentaria Especial",
    # Preventivas
    "P":   "Preventiva (general)",
    "PR":  "Preventiva por caracteristicas de la via",
    "PC":  "Preventiva por caracteristicas geometricas",
    "PI":  "Preventiva por interseccion",
    "PO":  "Preventiva por caracteristicas operativas",
    "PE":  "Preventiva por situaciones especiales",
    "PP":  "Preventiva relativa al pavimento",
    # Informativas
    "I":   "Informativa (general)",
    "IP":  "Informativa de Preseñalizacion",
    "ID":  "Informativa de Direccion",
    "IC":  "Informativa de Confirmacion",
    "IS":  "Informativa de Servicios",
    "IT":  "Informativa Turistica",
    "IR":  "Informativa de Ruta",
    # Trabajos en la via
    "TM":  "Senal Transitoria de Trabajos",
    "TP":  "Senal Preventiva de Trabajos",
    "TR":  "Senal Reglamentaria de Trabajos",
    # Demarcaciones / horizontales
    "D":   "Demarcacion horizontal",
}


# Regex robusto: detecta codigos como RP-1, RP-2a, IS-19, RPO-3, etc.
PATRON_CODIGO = re.compile(r"\b([A-Z]{1,4})-(\d+[a-z]?)\b")


# ─────────────────────────────────────────────────────────────────────────────
# CONEXION A CHROMA
# ─────────────────────────────────────────────────────────────────────────────
_collection = None

def _get_collection():
    global _collection
    if _collection is None:
        embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = client.get_or_create_collection(
            COLLECTION_NAME, embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACCION EXHAUSTIVA DE CODIGOS
# ─────────────────────────────────────────────────────────────────────────────
def construir_base_senales(forzar_recargar: bool = False) -> dict:
    """
    Recorre TODOS los fragmentos del manual y extrae cada codigo de senal
    con su contexto (texto cercano que probablemente contiene el nombre).

    Estructura retornada:
    {
        "RP-1": [
            {"texto": "...", "volumen": "Volumen 6", "pagina": "200-205"},
            ...
        ],
        "PI-2": [...],
        ...
    }
    """
    if CACHE_FILE.exists() and not forzar_recargar:
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    print("[signs_db] Construyendo base de senales (recorrido completo)...")

    col = _get_collection()
    todos = col.get(include=["documents", "metadatas"])
    docs = todos["documents"]
    metas = todos["metadatas"]

    base = {}  # codigo -> lista de apariciones

    for doc, meta in zip(docs, metas):
        for match in PATRON_CODIGO.finditer(doc):
            prefijo, numero = match.group(1), match.group(2)
            # Filtrar solo los prefijos del catalogo de senales
            if prefijo not in TIPOS_SEÑALES:
                continue

            codigo = f"{prefijo}-{numero}"

            # Extraer contexto: 60 chars antes y 100 despues
            inicio = max(0, match.start() - 60)
            fin = min(len(doc), match.end() + 100)
            contexto = doc[inicio:fin].strip()

            # Limpiar saltos de linea
            contexto = re.sub(r"\s+", " ", contexto)

            entrada = {
                "contexto": contexto,
                "volumen": meta.get("volumen", "N/D"),
                "pagina": f"{meta.get('pagina_inicio')}-{meta.get('pagina_fin')}",
            }

            if codigo not in base:
                base[codigo] = []

            # Evitar duplicados exactos
            if not any(e["contexto"] == entrada["contexto"] for e in base[codigo]):
                base[codigo].append(entrada)

    # Guardar cache
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(base, f, ensure_ascii=False, indent=2)
        print(f"[signs_db] Cache guardado: {CACHE_FILE.name} ({len(base)} codigos unicos)")
    except Exception as e:
        print(f"[signs_db] Error guardando cache: {e}")

    return base


# ─────────────────────────────────────────────────────────────────────────────
# CONSULTAS A LA BASE
# ─────────────────────────────────────────────────────────────────────────────
_cache_base = None

def _base():
    global _cache_base
    if _cache_base is None:
        _cache_base = construir_base_senales()
    return _cache_base


def listar_todas_senales() -> list[dict]:
    """
    Retorna lista completa de todas las senales encontradas, con:
    - codigo
    - tipo (categoria humana)
    - mejor_contexto (la frase mas representativa)
    - volumenes (donde aparece)
    """
    base = _base()
    resultado = []

    for codigo, apariciones in sorted(base.items(), key=lambda x: (x[0].split("-")[0], int(x[0].split("-")[1].rstrip("abcdefghij")) if x[0].split("-")[1].rstrip("abcdefghij") else 0)):
        prefijo = codigo.split("-")[0]
        tipo = TIPOS_SEÑALES.get(prefijo, "Otro")

        # Elegir el mejor contexto (el mas largo y mas legible)
        mejor = max(apariciones, key=lambda x: len(x["contexto"]))

        # Lista de volumenes/paginas distintos
        ubicaciones = list({(a["volumen"], a["pagina"]) for a in apariciones})

        resultado.append({
            "codigo": codigo,
            "tipo": tipo,
            "categoria_codigo": prefijo,
            "n_apariciones": len(apariciones),
            "contexto": mejor["contexto"],
            "ubicaciones": [f"{v}, pag. {p}" for v, p in ubicaciones[:3]],
        })

    return resultado


def listar_senales_por_categoria(categoria: str) -> list[dict]:
    """
    Retorna senales de una categoria especifica (ej: 'RP', 'PI', 'IS').
    """
    todas = listar_todas_senales()
    return [s for s in todas if s["categoria_codigo"] == categoria.upper()]


def buscar_senal(codigo: str) -> dict | None:
    """
    Busca informacion de un codigo especifico (ej: 'RP-1').
    """
    base = _base()
    if codigo in base:
        return {
            "codigo": codigo,
            "tipo": TIPOS_SEÑALES.get(codigo.split("-")[0], "Otro"),
            "apariciones": base[codigo],
        }
    return None


def estadisticas() -> dict:
    """Resumen estadistico de la base de senales."""
    base = _base()
    por_categoria = {}
    for cod in base.keys():
        prefijo = cod.split("-")[0]
        por_categoria[prefijo] = por_categoria.get(prefijo, 0) + 1

    return {
        "total_codigos_unicos": len(base),
        "total_apariciones": sum(len(v) for v in base.values()),
        "por_categoria": dict(sorted(por_categoria.items(), key=lambda x: -x[1])),
    }


# ─────────────────────────────────────────────────────────────────────────────
# FORMATEO PARA RESPUESTA
# ─────────────────────────────────────────────────────────────────────────────
def _extraer_nombre_corto(contexto: str, codigo: str) -> str:
    """
    Intenta extraer el nombre breve de la senal del contexto.
    Ej: contexto = '...IS-19 TELEFONO PUBLICO IS-20 TERMINAL...' -> 'TELEFONO PUBLICO'
    """
    # Buscar texto en mayusculas despues del codigo
    pos = contexto.find(codigo)
    if pos == -1:
        return ""
    despues = contexto[pos + len(codigo):pos + len(codigo) + 80]
    # Capturar palabras consecutivas en MAYUSCULA o capitalizadas
    match = re.match(r"\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s/.-]{2,40})", despues)
    if match:
        nombre = match.group(1).strip()
        # Cortar al primer salto de linea logico
        nombre = re.split(r"\s+(?:[A-Z]{1,4}-\d|EDICION|VOLUMEN|CAPITULO|MOP)", nombre)[0]
        return nombre.strip(" .,-")[:50]
    return ""


def formatear_listado_completo() -> str:
    """Genera un texto markdown COMPACTO con TODAS las senales encontradas."""
    todas = listar_todas_senales()

    # Agrupar por categoria
    por_cat = {}
    for s in todas:
        cat = s["categoria_codigo"]
        if cat not in por_cat:
            por_cat[cat] = []
        por_cat[cat].append(s)

    lineas = [f"# Listado de codigos de señales del Manual MOP ({len(todas)} codigos)\n"]

    orden_cat = ["R", "RP", "RPO", "RR", "RM", "RE",
                 "P", "PR", "PC", "PI", "PO", "PE", "PP",
                 "I", "IP", "ID", "IC", "IS", "IT", "IR",
                 "TM", "TP", "TR", "D"]

    for cat in orden_cat:
        if cat not in por_cat:
            continue
        senales = por_cat[cat]
        nombre_cat = TIPOS_SEÑALES.get(cat, "Otra")
        lineas.append(f"\n## {nombre_cat} ({cat}) — {len(senales)} codigos")

        # Lista compacta: codigo y nombre extraido (1 linea por codigo)
        for s in senales:
            nombre_corto = _extraer_nombre_corto(s["contexto"], s["codigo"])
            if nombre_corto:
                lineas.append(f"- `{s['codigo']}` — {nombre_corto}")
            else:
                lineas.append(f"- `{s['codigo']}`")

    return "\n".join(lineas)


def formatear_listado_completo_DETALLADO() -> str:
    """Version detallada con contexto (uso opcional, mas larga)."""
    todas = listar_todas_senales()
    por_cat = {}
    for s in todas:
        cat = s["categoria_codigo"]
        por_cat.setdefault(cat, []).append(s)

    lineas = [f"# Codigos de señales MOP ({len(todas)})\n"]
    orden_cat = ["R", "RP", "RPO", "RR", "RM", "RE", "P", "PR", "PC", "PI", "PO", "PE", "PP",
                 "I", "IP", "ID", "IC", "IS", "IT", "IR", "TM", "TP", "TR", "D"]
    for cat in orden_cat:
        if cat not in por_cat: continue
        senales = por_cat[cat]
        lineas.append(f"\n## {TIPOS_SEÑALES.get(cat, '?')} ({cat})\n")
        for s in senales:
            lineas.append(f"- **{s['codigo']}** — {s['contexto'][:100]}...")
    return "\n".join(lineas)


def formatear_listado_por_categoria(categoria: str) -> str:
    """Genera markdown de una categoria especifica."""
    senales = listar_senales_por_categoria(categoria)
    if not senales:
        return f"No se encontraron senales de la categoria '{categoria}'."

    nombre_cat = TIPOS_SEÑALES.get(categoria.upper(), "Categoria")
    lineas = [f"# Señales {nombre_cat} ({categoria.upper()})\n"]
    lineas.append(f"Total: **{len(senales)} códigos** encontrados.\n")

    for s in senales:
        lineas.append(f"\n### {s['codigo']}")
        lineas.append(f"{s['contexto']}")
        lineas.append(f"*{s['ubicaciones'][0]}*")

    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────────────
# CLI para probar
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print("=== Construyendo base de senales ===")
    construir_base_senales(forzar_recargar=True)

    print("\n=== Estadisticas ===")
    stats = estadisticas()
    print(f"Total codigos unicos: {stats['total_codigos_unicos']}")
    print(f"Total apariciones:    {stats['total_apariciones']}")
    print(f"\nPor categoria:")
    for cat, n in stats["por_categoria"].items():
        nombre = TIPOS_SEÑALES.get(cat, "?")
        print(f"  {cat:5s} = {n:3d} codigos  ({nombre})")
