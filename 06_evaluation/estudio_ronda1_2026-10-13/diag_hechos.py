# Solo lectura. «Hechos decisivos → delitos candidatos»: el LLM (prompt genérico, sin conocer el caso) lista los
# hechos jurídicamente relevantes y los delitos posibles; esa lista se busca como sub-consulta extra (denso + BM25)
# y se fusiona por RRF con la búsqueda normal. ¿Sube la Ley de Extorsión (art. 15/17) y el Quinquies?
import sys, json, io, contextlib, statistics as st
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
import os; os.chdir('/home/tlacua/apps/RAG_lab/apps/rewrite_lab')
from dotenv import load_dotenv; load_dotenv('.env')
os.environ['GOOGLE_CLIENT_ID'] = ''
with contextlib.redirect_stdout(io.StringIO()):
    import main as M
from shared.db import connect
ART = {30846: 'Quáter', 30847: 'Quinquies', 37759: 'LG15', 37761: 'LG17'}
TOPIC = 'derecho_penal_mexicano'
SYS = 'Eres un penalista mexicano. Analizas hechos narrados por personas sin formación jurídica.'
PROMPT = ("Lee lo que cuenta la persona. En 3 a 5 líneas: (1) enumera los HECHOS que pueden cambiar qué delito es "
          "(qué se hizo, si se pide dinero u otro beneficio, si hubo consentimiento, relación entre las personas, lugar, "
          "edad); (2) nombra en términos jurídicos los delitos que podrían configurarse. No cites artículos.\n\nRELATO:\n")
with connect() as c, c.cursor() as cur:
    cur.execute("""select t.pregunta, t.busqueda_debug from estudio_turnos t join estudio_intentos i on i.id=t.intento_id
                   where i.escenario='fotos' and t.n=1 and i.codigo <> all(%s) order by t.id""", (['NGSX-GGPH', 'K9TQ-6P86', 'FYJ2-VS7R'],))
    filas = cur.fetchall()
    pref = M.query_prefix(M.instruct_for(TOPIC))
    def rk(ids): return {a: (ids.index(i) + 1 if i in ids else 999) for i, a in ART.items()}
    pos = {'base': {a: [] for a in ART.values()}, 'base+hechos': {a: [] for a in ART.values()}}
    ejemplos = []
    for q, dbg in filas:
        dbg = dbg if isinstance(dbg, dict) else (json.loads(dbg) if dbg else {})
        hp = dbg.get('hyde_passage') or next((s.get('hyde_passage') for s in dbg.get('subs') or [] if s and s.get('hyde_passage')), None)
        dh = M.dense_ranked(cur, M.tei.embed([pref + q + ('\n\n' + hp if hp else '')], use_cache=False)[0], TOPIC)
        base = [i for i, _ in M.rrf_scored([[i for i, _ in dh], [i for i, _ in M.bm25_ranked(q, TOPIC)]])]
        h = M.llm.chat(SYS, PROMPT + q, temperature=0, max_tokens=250, timeout=300)
        dx = M.dense_ranked(cur, M.tei.embed([pref + h], use_cache=False)[0], TOPIC)
        extra = [i for i, _ in M.rrf_scored([[i for i, _ in dx], [i for i, _ in M.bm25_ranked(h, TOPIC)]])]
        # intercalar como hace decompose: base[0], extra[0], base[1], extra[1]…
        mix, seen = [], set()
        for a, b in zip(base, extra + [None] * len(base)):
            for x in (a, b):
                if x is not None and x not in seen: seen.add(x); mix.append(x)
        for k, ids in (('base', base), ('base+hechos', mix)):
            for a, p in rk(ids).items(): pos[k][a].append(p)
        ejemplos.append((q[:90], h))
for q, h in ejemplos[:4]: print('Q:', q, '\n  →', h.replace('\n', ' | '), '\n')
print('preguntas:', len(filas))
for k in pos:
    print(k, {a: dict(mediana=st.median(xs), top10=sum(x <= 10 for x in xs), top3=sum(x <= 3 for x in xs)) for a, xs in pos[k].items()})
json.dump(dict(pos=pos, ejemplos=ejemplos), open('/tmp/diag_hechos.json', 'w'), ensure_ascii=False)
