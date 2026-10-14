# Solo lectura. Simula «descripción en lenguaje cotidiano» por artículo: el LLM la genera con un prompt
# neutro (sin conocer el caso), se embebe texto+descripción y se mide en qué posición quedaría cada artículo
# en el ranking denso (+HyDE guardado) de las preguntas de «Las fotos», sin tocar la base.
import sys, json, io, contextlib, statistics as st, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
import os; os.chdir('/home/tlacua/apps/RAG_lab/apps/rewrite_lab')
from dotenv import load_dotenv; load_dotenv('.env')
os.environ['GOOGLE_CLIENT_ID'] = ''
with contextlib.redirect_stdout(io.StringIO()):
    import main as M
import numpy as np
from shared.db import connect
ART = {30846: 'Quáter', 30847: 'Quinquies', 37759: 'LG15', 37761: 'LG17', 30845: 'Ter', 30844: 'Bis'}
TOPIC = 'derecho_penal_mexicano'
PROMPT = ("Explica en 2 o 3 frases, en español cotidiano y sin tecnicismos, qué conducta castiga este artículo, "
          "con las palabras que usaría una persona común para contar que le pasó (sin mencionar números de artículo). "
          "Responde solo la explicación.\n\nARTÍCULO:\n")
def gen(texto):
    out = M.llm.chat('Eres un asistente que explica leyes en lenguaje sencillo.', PROMPT + texto, temperature=0, max_tokens=250, timeout=300)
    assert out, 'descripción vacía'
    return out
with connect() as c, c.cursor() as cur:
    cur.execute(f"select id, text from {M.TABLE} where id = any(%s)", (list(ART),))
    textos = dict(cur.fetchall())
    desc = {i: gen(textos[i]) for i in ART}
    for i in ART: print(f"[{ART[i]}] {desc[i]}\n")
    docv = {i: np.array(M.tei.embed([textos[i]], use_cache=False)[0]) for i in ART}            # como está indexado
    docd = {i: np.array(M.tei.embed([textos[i] + '\n\nEn palabras sencillas: ' + desc[i]], use_cache=False)[0]) for i in ART}
    cur.execute("""select t.pregunta, t.busqueda_debug from estudio_turnos t join estudio_intentos i on i.id=t.intento_id
                   where i.escenario='fotos' and t.n=1 and i.codigo <> all(%s) order by t.id""", (['NGSX-GGPH', 'K9TQ-6P86', 'FYJ2-VS7R'],))
    filas = cur.fetchall()
    pref = M.query_prefix(M.instruct_for(TOPIC))
    pos = {k: {a: [] for a in ART.values()} for k in ('original', 'con_desc')}
    for q, dbg in filas:
        dbg = dbg if isinstance(dbg, dict) else (json.loads(dbg) if dbg else {})
        hp = dbg.get('hyde_passage') or next((s.get('hyde_passage') for s in dbg.get('subs') or [] if s and s.get('hyde_passage')), None)
        qv = M.tei.embed([pref + q + ('\n\n' + hp if hp else '')], use_cache=False)[0]
        lista = M.dense_ranked(cur, qv, TOPIC)          # [(id, dist)] top N_DENSE, ya ordenado
        qn = np.array(qv)
        for i, a in ART.items():
            otros = [d for j, d in lista if j not in ART]   # el resto del corpus queda igual
            for k, v in (('original', docv[i]), ('con_desc', docd[i])):
                dist = 1 - float(qn @ v / (np.linalg.norm(qn) * np.linalg.norm(v)))
                pos[k][a].append(1 + sum(1 for d in otros if d < dist))
print('preguntas:', len(filas), '(1.ª pregunta, denso+HyDE; posición frente al resto del corpus; tope', M.N_DENSE, ')')
for k in pos:
    print(k, {a: dict(mediana=st.median(xs), top10=sum(x <= 10 for x in xs), top3=sum(x <= 3 for x in xs)) for a, xs in pos[k].items()})
json.dump(dict(desc={ART[i]: desc[i] for i in ART}, pos=pos), open('/tmp/diag_desc.json', 'w'), ensure_ascii=False)
