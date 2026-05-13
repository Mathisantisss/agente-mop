"""
Agente RAG mejorado: busqueda agresiva con expansion de queries,
prompts permisivos para sintesis multi-fragmento, y datos estructurados
de senales para precision 100% en consultas sobre nomenclatura.
"""

import re
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from config import (
    CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL, TOP_K,
)

# Importar base de senales estructurada (datos deterministicos)
try:
    from signs_db import (
        listar_todas_senales,
        listar_senales_por_categoria,
        formatear_listado_completo,
        formatear_listado_por_categoria,
        TIPOS_SEÑALES,
    )
    SIGNS_DB_DISPONIBLE = True
except ImportError:
    SIGNS_DB_DISPONIBLE = False

# ─────────────────────────────────────────────────────────────────────────────
# ChromaDB
# ─────────────────────────────────────────────────────────────────────────────
_collection = None


def get_collection():
    global _collection
    if _collection is None:
        embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


# ─────────────────────────────────────────────────────────────────────────────
# EXPANSION DE QUERIES — Genera variaciones de la consulta original
# ─────────────────────────────────────────────────────────────────────────────
SINONIMOS = {
    "señaletica":     ["señalizacion", "señales", "demarcaciones", "signos viales"],
    "señaletica":     ["señalizacion", "señales"],
    "señalizacion":   ["señales", "señaletica", "demarcaciones"],
    "señales":        ["señalizacion", "señaletica"],
    "codigo":         ["nomenclatura", "clasificacion", "tipo"],
    "tipo":           ["clasificacion", "categoria", "codigo"],
    "listado":        ["listа", "catalogo", "inventario", "tabla"],
    "carretera":      ["camino", "via", "ruta"],
    "pavimento":      ["calzada", "rodadura", "superficie"],
    "curva":          ["curvatura", "trazado curvo", "alineamiento"],
    "drenaje":        ["evacuacion de aguas", "alcantarilla", "cuneta"],
    "puente":         ["estructura", "obra de arte", "viaducto"],
    "señalizacion vertical":   ["señales verticales", "PARE", "CEDA EL PASO"],
    "señalizacion horizontal": ["demarcaciones", "lineas pavimento"],
    "diseño":         ["dimensionamiento", "proyecto"],
    "norma":          ["criterio", "especificacion", "requisito"],
    "velocidad":      ["velocidad de diseño", "velocidad maxima"],
}


def expandir_query(consulta: str) -> list[str]:
    """
    Genera multiples variaciones de la consulta para mejorar recall.
    Retorna la query original + 1-3 variaciones con sinonimos.
    """
    consulta_lower = consulta.lower()
    queries = [consulta]
    variaciones = set()

    for termino, sinonimos in SINONIMOS.items():
        if termino in consulta_lower:
            for sin in sinonimos[:2]:  # max 2 sinonimos por termino
                nueva = re.sub(re.escape(termino), sin, consulta_lower, flags=re.IGNORECASE)
                if nueva != consulta_lower and nueva not in variaciones:
                    variaciones.add(nueva)

    queries.extend(list(variaciones)[:3])  # max 3 variaciones extra
    return queries


# ─────────────────────────────────────────────────────────────────────────────
# BUSQUEDA AGRESIVA — Multi-query con deduplicacion
# ─────────────────────────────────────────────────────────────────────────────
def detectar_consulta_senales(consulta: str) -> dict:
    """
    Detecta si la consulta es sobre senales y, en ese caso, que tipo.
    Retorna {'es_senales': bool, 'categoria': 'RP'|'PI'|...|None, 'completa': bool}
    """
    t = consulta.lower()
    palabras_senales = ["señal", "senal", "señaletica", "senaletica", "señalizacion",
                        "senalizacion", "demarcacion", "codigo de senal", "tipos de senal",
                        "listado de senal"]
    es_senales = any(p in t for p in palabras_senales)

    # Detectar categoria especifica mencionada
    categoria = None
    categorias_keywords = {
        "RP":  ["reglamentaria de prioridad", "PARE", "CEDA"],
        "RPO": ["prohibicion", "prohibido", "no virar"],
        "RR":  ["restriccion", "velocidad maxima"],
        "PI":  ["interseccion", "cruce"],
        "IS":  ["informativa de servicio", "servicios", "telefono", "hospital"],
        "ID":  ["informativa de direccion", "direccion"],
        "IP":  ["preseñalizacion", "preselizacion"],
        "D":   ["demarcacion horizontal", "lineas pavimento"],
        "TM":  ["trabajos en la via", "transitoria"],
    }
    for cat, kws in categorias_keywords.items():
        if any(k.lower() in t for k in kws):
            categoria = cat
            break

    # Detectar si pide un listado completo
    triggers_completo = ["todas las", "todos los", "listado completo", "lista de todas",
                         "completo", "exhaustivo", "todas", "todos"]
    completa = any(tr in t for tr in triggers_completo)

    return {"es_senales": es_senales, "categoria": categoria, "completa": completa}


def buscar_contexto(
    consulta: str,
    volumen: str = "",
    n_resultados: int = 12,           # ↑ subido de 5 a 12
    umbral_relevancia: float = 30.0,  # ↓ bajado de 40 a 30
    max_chars: int = 1500,            # ↑ subido de 600 a 1500
) -> list[dict]:
    """
    Busqueda multi-query con deduplicacion y mas contexto por fragmento.

    Si detecta que la consulta es sobre senales, INYECTA automaticamente
    datos estructurados (deterministicos) de la base de senales para
    garantizar precision en codigos y nombres.
    """
    collection = get_collection()
    if collection.count() == 0:
        return []

    where = {"volumen": {"$eq": volumen}} if volumen else None

    # Expandir query y buscar todas las variaciones
    queries = expandir_query(consulta)
    todos_resultados = []  # lista de (chunk_id, doc, meta, dist)
    ids_vistos = set()

    for q in queries:
        try:
            results = collection.query(
                query_texts=[q],
                n_results=min(n_resultados, collection.count()),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            continue

        ids = results.get("ids", [[]])[0]
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]

        for cid, doc, meta, dist in zip(ids, docs, metas, dists):
            if cid in ids_vistos:
                continue
            ids_vistos.add(cid)
            todos_resultados.append((cid, doc, meta, dist))

    # Ordenar por distancia (menor distancia = mayor relevancia)
    todos_resultados.sort(key=lambda x: x[3])

    # Filtrar por umbral y construir lista final
    fragmentos = []
    for cid, doc, meta, dist in todos_resultados[: n_resultados * 2]:
        relevancia = max(0, (1 - dist) * 100)
        if relevancia < umbral_relevancia:
            break
        texto = doc.strip()
        if len(texto) > max_chars:
            texto = texto[:max_chars] + "..."
        fragmentos.append({
            "texto": texto,
            "volumen": meta.get("volumen", "N/D"),
            "pag_inicio": meta.get("pagina_inicio", "?"),
            "pag_fin": meta.get("pagina_fin", "?"),
            "relevancia": relevancia,
        })
        if len(fragmentos) >= n_resultados:
            break

    # ─── INYECCION DE DATOS ESTRUCTURADOS DE SEÑALES ───
    if SIGNS_DB_DISPONIBLE:
        deteccion = detectar_consulta_senales(consulta)
        if deteccion["es_senales"]:
            try:
                if deteccion["categoria"]:
                    texto_estructurado = formatear_listado_por_categoria(deteccion["categoria"])
                else:
                    texto_estructurado = formatear_listado_completo()

                fragmento_vip = {
                    "texto": (
                        "[LISTADO OFICIAL EXTRAIDO DEL MANUAL - PRECISION 100%]\n\n"
                        + texto_estructurado
                    ),
                    "volumen": "Manual MOP (todos los volumenes)",
                    "pag_inicio": "—",
                    "pag_fin": "—",
                    "relevancia": 100.0,
                }
                fragmentos.insert(0, fragmento_vip)

                # IMPORTANTE: cuando inyectamos datos estructurados, REDUCIMOS
                # el resto de fragmentos para no exceder el contexto del modelo.
                # Quedamos con el VIP + 2 fragmentos semanticos cortos.
                fragmentos = [fragmentos[0]] + [
                    {**f, "texto": f["texto"][:600] + ("..." if len(f["texto"]) > 600 else "")}
                    for f in fragmentos[1:3]
                ]
            except Exception as e:
                print(f"[local_agent] Error al inyectar señales: {e}")

    return fragmentos


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT DE SISTEMA — Permisivo, anima la sintesis de multiples fragmentos
# ─────────────────────────────────────────────────────────────────────────────
def construir_prompt_sistema() -> str:
    return """Eres un experto senior del Ministerio de Obras Publicas (MOP) de Chile, \
especialista en el Manual de Carreteras (Edicion Junio 2025) y la normativa vial chilena.

# Tus capacidades
Tienes acceso al texto completo de los 9 volumenes del Manual MOP a traves de fragmentos \
recuperados desde una base vectorial. Tu mision es sintetizar la mejor respuesta posible \
combinando informacion de MULTIPLES fragmentos.

# Como debes responder
1. **SIEMPRE intenta responder.** Aunque los fragmentos no contengan la respuesta completa, \
   extrae todo lo util y entrega una respuesta lo mas completa posible.

2. **Sintetiza informacion de varios fragmentos.** Si la respuesta requiere combinar datos \
   de fragmentos diferentes, hazlo activamente. No esperes encontrar todo en un solo lugar.

3. **Para listados (señales, codigos, normas, etc.):** Si el usuario pide un listado o \
   tabla y los fragmentos contienen informacion parcial, entrega lo que encuentres y \
   menciona explicitamente que es parcial. Organiza la respuesta por categorias claras.

4. **Cita siempre las fuentes:** Al final de cada bloque o afirmacion tecnica importante, \
   incluye la cita en formato: (Manual MOP, Volumen X, pag. Y) o (Manual MOP, Volumen X, \
   pags. Y-Z) si abarca varias paginas.

5. **Estructura tu respuesta:**
   - Usa encabezados (## Titulo, ### Subtitulo) para secciones
   - Usa listas con viñetas (-) para enumeraciones
   - Usa **negrita** para terminos tecnicos clave
   - Si entregas codigos o nomenclaturas, presentalos en una lista clara

6. **Cuando los fragmentos sean realmente insuficientes:**
   - Indica QUE informacion especifica falta
   - Sugiere QUE volumenes o secciones del manual contienen probablemente la respuesta \
     completa
   - NO digas simplemente "no hay informacion" si tienes datos parciales — entregalos

7. **Idioma:** Responde SIEMPRE en español tecnico chileno.

8. **Precision:** No inventes valores numericos, codigos o normas que no esten en los \
   fragmentos. Pero SI puedes describir conceptos generales y referencias a temas \
   relacionados que aparezcan en los fragmentos."""


# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUCCION DE MENSAJES PARA EL LLM
# ─────────────────────────────────────────────────────────────────────────────
def construir_prompt_con_contexto(
    pregunta: str,
    fragmentos: list[dict],
    historial: list[dict],
) -> list[dict]:
    """Construye los mensajes para el LLM con contexto enriquecido."""

    # Bloque de contexto del manual
    if fragmentos:
        # ¿Hay un fragmento de datos estructurados (relevancia 100%)?
        tiene_estructurado = any(
            "DATOS ESTRUCTURADOS" in f.get("texto", "") for f in fragmentos
        )

        ctx = ["## Fragmentos relevantes recuperados del Manual MOP\n"]
        ctx.append(f"Total: {len(fragmentos)} fragmentos.\n")

        if tiene_estructurado:
            ctx.append(
                "\n**IMPORTANTE:** El primer fragmento contiene DATOS ESTRUCTURADOS "
                "extraidos deterministicamente (precision 100%). "
                "USA ESE FRAGMENTO COMO FUENTE PRINCIPAL para listados de codigos y nombres. "
                "Los demas fragmentos son contexto adicional para enriquecer descripciones.\n"
            )
        else:
            ctx.append("Sintetiza la respuesta combinando la informacion de TODOS los fragmentos relevantes.\n")

        for i, f in enumerate(fragmentos, 1):
            ctx.append(
                f"\n### [Fragmento {i}] {f['volumen']} — paginas {f['pag_inicio']} a {f['pag_fin']} "
                f"(relevancia {f['relevancia']:.0f}%)\n```\n{f['texto']}\n```\n"
            )
        contexto = "\n".join(ctx)
    else:
        contexto = (
            "## Sin fragmentos relevantes recuperados\n\n"
            "No se encontraron fragmentos con suficiente relevancia para esta consulta. "
            "Indica al usuario que reformule su pregunta o que la informacion no esta en la base."
        )

    # Mensaje del usuario enriquecido
    mensaje_usuario = (
        f"{contexto}\n\n"
        f"---\n\n"
        f"## Consulta del usuario\n"
        f"{pregunta}\n\n"
        f"Responde de forma completa, sintetizando la informacion de los fragmentos. "
        f"Cita siempre las paginas y volumenes."
    )

    mensajes = [{"role": "system", "content": construir_prompt_sistema()}]

    # Historial conversacional reciente (sin contexto repetido)
    for msg in historial[-6:]:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            mensajes.append({"role": msg["role"], "content": msg["content"]})

    mensajes.append({"role": "user", "content": mensaje_usuario})
    return mensajes


# ─────────────────────────────────────────────────────────────────────────────
# DETECCION DE SOLICITUD DE ARCHIVO
# ─────────────────────────────────────────────────────────────────────────────
def detectar_solicitud_archivo(texto: str) -> dict:
    """Detecta si el usuario pide un Excel o Word."""
    t = texto.lower()
    result = {"excel": False, "word": False}

    palabras_excel = ["excel", "planilla", "tabla en excel", "xlsx", "hoja de calculo",
                      "spreadsheet", ".xlsx", "exportar a excel"]
    palabras_word  = ["word", ".docx", "informe word", "reporte word", "memoria tecnica",
                      "documento word"]

    if any(p in t for p in palabras_excel):
        result["excel"] = True
    if any(p in t for p in palabras_word):
        result["word"] = True

    # Heuristica adicional: si pide "listado/listа detallado" + sin extension explicita
    # y la respuesta es larga, probablemente quiere Excel
    if not result["excel"] and not result["word"]:
        triggers_excel = ["listado detallado", "listа completa", "todos los", "tabla con",
                          "comparativo", "dame todos", "necesito un excel"]
        if any(t2 in t for t2 in triggers_excel):
            result["excel"] = True

    return result
