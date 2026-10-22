"""Tiempos por etapa de la matriz 2026-10-21: media, desviación estándar, mediana y p90 por pregunta (sets 3, 13 y 14;
set 12 aparte). Cada fila de bench_results guarda los segundos de cada etapa en `timings`."""
import sys, re, json, statistics as st
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
with connect() as c, c.cursor() as cur:
    cur.execute("select b.set_id, b.label, r.timings from bench_results r join bench_runs b on b.id = r.run_id "
                "where b.label like 'matriz-2026-10-21%%' and r.error is null and r.timings is not null")
    filas = cur.fetchall()
def cfg(label): return re.search(r'· (\w+) ', label).group(1)
def resumen(v):
    v = sorted(v); n = len(v)
    return {'n': n, 'media': round(st.mean(v), 2), 'std': round(st.stdev(v), 2), 'p50': round(v[n // 2], 2),
            'p90': round(v[int(n * 0.9)], 2)}
grupos = {}
def add(clave, x): grupos.setdefault(clave, []).append(x)
for sid, label, t in filas:
    g = 'set12' if sid == 12 else 'grandes'; c = cfg(label)
    for etapa in ('filtro', 'descomponer', 'por_delito', 'remisiones', 'juez'):
        if etapa in t: add((g, etapa, 'todas'), t[etapa])
    add((g, 'busqueda', c), t['busqueda'])
    add((g, 'respuesta', c), t['respuesta'])
    add((g, 'total_sin_juez', c), sum(v for k, v in t.items() if k != 'juez'))
out = {f'{g}|{e}|{c}': resumen(v) for (g, e, c), v in grupos.items() if len(v) > 1}
print(json.dumps(out, ensure_ascii=False))
