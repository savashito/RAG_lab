"""Carga los casos de la prueba «💬 Reescritura multiturno · recall» (🧩 Componentes) DIRECTO en la base (comp_casos):
cada mensaje siguiente (2.º o después) de las conversaciones de la ronda 1 (piloto_penal) y, aparte, la conversación de
prueba del usuario en la ronda 2 («fotos» → «Queretaro», turno 188). Son mensajes de participantes: no van al repo.
Solo carga si el componente no tiene casos.   python sembrar_reescritura.py"""
import json, sys, os
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
os.chdir('/home/tlacua/apps/RAG_lab/apps/rewrite_lab')
from dotenv import load_dotenv; load_dotenv('.env')
from shared.db import connect
EXTRA = [(188, 'Prueba del usuario en la ronda 2 (24-oct): el asistente preguntó el estado y la persona respondió solo «Queretaro».')]
with connect() as c, c.cursor() as cur:
    cur.execute("SELECT 1 FROM comp_casos WHERE componente = 'reescritura_recall' LIMIT 1")
    if cur.fetchone():
        sys.exit('ya tiene casos: no se toca')
    cur.execute("SELECT t.id, t.pregunta, i.escenario, i.variante, t.n FROM estudio_turnos t JOIN estudio_intentos i ON i.id = t.intento_id "
                "JOIN estudio_codigos k ON k.codigo = i.codigo WHERE k.estudio = 'piloto_penal' AND t.n >= 2 ORDER BY t.id")
    filas = [(tid, p, f'ronda 1 · {esc}{" " + var if var else ""} · mensaje {n}', None) for tid, p, esc, var, n in cur.fetchall()]
    for tid, nota in EXTRA:
        cur.execute('SELECT pregunta FROM estudio_turnos WHERE id = %s', (tid,))
        r = cur.fetchone()
        if r:
            filas.append((tid, r[0], 'ronda 2 · prueba del usuario', nota))
    for tid, p, fuente, nota in filas:
        cur.execute("INSERT INTO comp_casos (componente, entrada, esperado, fuente, nota, revisado, creado_por) VALUES "
                    "('reescritura_recall', %s, %s::jsonb, %s, %s, true, 'sembrar_reescritura.py')",
                    (p, json.dumps({'turno_id': tid}), fuente, nota))
    c.commit()
print(f'{len(filas)} casos cargados')
