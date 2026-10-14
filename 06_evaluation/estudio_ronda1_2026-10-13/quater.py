# Solo lectura: en «Las fotos», ¿qué artículos 167 (Quáter / Quinquies) de Querétaro y de la Ley General de
# Extorsión trajo la búsqueda (posición en el ranking y si llegaron al contexto) y cuál citó el asistente?
import sys, re
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv('apps/rewrite_lab/.env')
from shared.db import connect
from shared.code_routes import fold
T = 'sistema_penal__qwen06__legal'
with connect() as c, c.cursor() as cur:
    cur.execute(f"select id, hierarchy from {T} where source='Código Penal del Estado de Querétaro.md' and hierarchy ~* 'art[íi]culo 167 (qu[aá]ter|quinquies)$'")
    arts = {i: h.split(' > ')[-1] for i, h in cur.fetchall()}
    cur.execute(f"select id, hierarchy from {T} where source ilike '%%Extorsión%%' and hierarchy ~* 'art[íi]culo (15|17)$'")
    arts.update({i: 'LGExt ' + h.split(' > ')[-1] for i, h in cur.fetchall()})
    print('chunks:', arts)
    cur.execute("""select p.fase, p.condicion, t.n, t.pregunta, t.ranking, t.contexto, t.respuesta from estudio_turnos t join estudio_intentos i on i.id=t.intento_id
                   join estudio_participantes p using (codigo) where i.escenario='fotos' and t.respuesta is not null
                   and p.codigo <> all(%s) order by t.ts""", (['NGSX-GGPH', 'K9TQ-6P86', 'FYJ2-VS7R'],))
    filas = cur.fetchall()
cnt = {'cita_quater': 0, 'cita_quinquies': 0, 'cita_lg15': 0}
for fase, cond, n, q, rk, ctx, a in filas:
    pos = {arts[i]: rk.index(i) + 1 for i in arts if i in (rk or [])}
    enctx = sorted({arts[x['id']] for x in (ctx or []) if x.get('id') in arts})
    t = fold(a)
    cq, cqq = bool(re.search(r'167\s*quater', t)), bool(re.search(r'167\s*quinquies', t))
    clg = bool(re.search(r'art(iculo|\.)?\s*15\b', t)) and 'extorsion' in t
    cnt['cita_quater'] += cq; cnt['cita_quinquies'] += cqq; cnt['cita_lg15'] += clg
    print(f"\n[{fase}/{cond or '-'} t{n}] {q[:90]}\n   ranking(top50): {pos} | en contexto: {enctx} | cita: {'Quáter ' if cq else ''}{'Quinquies ' if cqq else ''}{'LG-art15' if clg else ''}")
print('\nrespuestas:', len(filas), cnt)
