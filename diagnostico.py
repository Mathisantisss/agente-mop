"""Test de la nueva busqueda mejorada."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from local_agent import buscar_contexto, expandir_query

consulta = "necesito un listado del tipo de senaletica, su codigo y nombre de senaletica de forma ordenada"

print(f"CONSULTA ORIGINAL:\n  {consulta}\n")
print(f"QUERIES EXPANDIDAS:")
for q in expandir_query(consulta):
    print(f"  - {q}")

print(f"\n{'='*60}")
print(f"FRAGMENTOS RECUPERADOS (top 12):")
print(f"{'='*60}\n")

frags = buscar_contexto(consulta, n_resultados=12)
print(f"Total: {len(frags)} fragmentos\n")

for i, f in enumerate(frags, 1):
    print(f"[{i}] {f['volumen']} pags {f['pag_inicio']}-{f['pag_fin']} | rel {f['relevancia']:.0f}%")
    texto = f['texto'][:180].replace('\n', ' ')
    print(f"    {texto}...\n")
