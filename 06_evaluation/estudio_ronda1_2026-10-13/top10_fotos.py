# Solo lectura: qué documentos ocupan el top-10 de la búsqueda en «Las fotos» y dónde queda la Ley de Extorsión.
import sys
from collections import Counter
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv('apps/rewrite_lab/.env')
from shared.db import connect
T = 'sistema_penal__qwen06__legal'
with connect() as c, c.cursor() as cur:
    cur.execute("""select t.ranking, t.pregunta from estudio_turnos t join estudio_intentos i on i.id=t.intento_id join estudio_participantes p using (codigo)
                   where i.escenario='fotos' and t.n=1 and t.ranking is not null and p.codigo <> all(%s)""", (['NGSX-GGPH','K9TQ-6P86','FYJ2-VS7R'],))
    filas = cur.fetchall()
    ids = {i for r, _ in filas for i in (r or [])[:10]}
    cur.execute(f"select id, source, split_part(hierarchy, ' > ', -1) from {T} where id = any(%s)", (list(ids),))
    info = {i: (s, h) for i, s, h in cur.fetchall()}
    cur.execute(f"select id from {T} where source ilike '%%Extorsión%%'"); lg = {r[0] for r in cur.fetchall()}
    cur.execute(f"select count(*), sum(length(text)) from {T} where source ilike '%%Extorsión%%'"); print('Ley de Extorsión en el corpus: chunks, caracteres =', cur.fetchone())
    cur.execute(f"select split_part(hierarchy,' > ',-1), left(regexp_replace(text, '\\s+', ' ', 'g'), 400) from {T} where source ilike '%%Extorsión%%' and hierarchy ~* 'art[íi]culo (15|17)$'")
    for h, t in cur.fetchall(): print(' ', h, '→', t[:400])
src = Counter(); docs_top = Counter(); mejor_lg = []
for r, q in filas:
    top = (r or [])[:10]
    for i in top:
        s, h = info.get(i, ('?', '?')); src[s] += 1
    pos = [k + 1 for k, i in enumerate(r or []) if i in lg]
    mejor_lg.append(pos[0] if pos else None)
print(f'\nprimeras preguntas: {len(filas)} · posición del 1er chunk de la Ley de Extorsión en el ranking (top-50):', mejor_lg)
print('documentos que ocupan el top-10 (veces):')
for s, n in src.most_common(15): print(f'  {n:3}  {s}')
