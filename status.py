"""
Script de estado: muestra el progreso de la ingesta y el estado de ChromaDB.
Uso:
    python status.py
"""
from pathlib import Path
import chromadb
from config import CHROMA_DIR, COLLECTION_NAME, REPORTS_DIR

LOG = Path(__file__).parent / "ingest_log.txt"


def mostrar_estado():
    print("\n=== Estado del Agente MOP ===\n")

    # Estado de la ingesta (log)
    if LOG.exists():
        lineas = LOG.read_text(encoding="utf-8", errors="ignore").splitlines()
        oks = [l for l in lineas if "[OK]" in l]
        errores = [l for l in lineas if "[ERROR]" in l]
        en_proceso = [l for l in lineas if l.strip().startswith("[") and "/9]" in l]

        print("--- Ingesta ---")
        for ok in oks:
            print(" ", ok.strip())
        if errores:
            for err in errores:
                print(" ", err.strip())
        if en_proceso:
            ultimo = en_proceso[-1].strip()
            if not any(ok_v in ultimo for ok_v in [ok.split("Volumen")[1].split()[0] for ok in oks if "Volumen" in ok]):
                print(f"  En proceso: {ultimo}")

        completada = any("completada" in l.lower() for l in lineas)
        if completada:
            total_lineas = [l for l in lineas if "Total en la base" in l]
            if total_lineas:
                print(f"\n  {total_lineas[-1].strip()}")
            print("\n  [INGESTA TERMINADA]")
        else:
            print("\n  [INGESTA EN CURSO...]")
    else:
        print("  No se encontro log de ingesta. Ejecuta: python ingest.py")

    # Estado ChromaDB
    print("\n--- Base de Datos (ChromaDB) ---")
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        col = client.get_collection(COLLECTION_NAME)
        total = col.count()
        print(f"  Fragmentos indexados: {total:,}")

        # Contar por volumen
        metas = col.get(include=["metadatas"])["metadatas"]
        volumes: dict[str, int] = {}
        for m in metas:
            v = m.get("volumen", "Sin clasificar")
            volumes[v] = volumes.get(v, 0) + 1
        for vol, cnt in sorted(volumes.items()):
            print(f"    {vol}: {cnt:,} fragmentos")
    except Exception as e:
        print(f"  No disponible: {e}")

    # Reportes generados
    print("\n--- Reportes Generados ---")
    reportes = list(REPORTS_DIR.glob("*.xlsx")) + list(REPORTS_DIR.glob("*.docx"))
    if reportes:
        for r in sorted(reportes, key=lambda x: x.stat().st_mtime, reverse=True):
            size_kb = r.stat().st_size // 1024
            print(f"  {r.name} ({size_kb} KB)")
    else:
        print("  Sin reportes generados aun.")

    print()


if __name__ == "__main__":
    mostrar_estado()
