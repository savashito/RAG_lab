"""Prueba de la llamada de RESPUESTA (sin LLM ni juez: lee corridas guardadas). Mide tres objetivos del prompt, con regex:
1. Pedir el estado: si la instrucción del filtro dice que pregunte el estado, ¿la respuesta lo pregunta? Y si el estado ya
   se conoce («No vuelvas a preguntar el estado»), ¿lo vuelve a preguntar?
2. Dar las penas: si el CONTEXTO trae una pena («… años de prisión»), ¿la respuesta da una pena?
3. Citar solo lo del contexto: % de citas sin respaldo (verificador de citas guardado en cada corrida).
Compara penal-original-v1 (C·v2: #155/#171 set 3, #156/#172 set 13, #157/#173 set 14, #158/#174 set 12) con
tlacua-v1-penas (D·v2: #159–#162, #175–#178): son iguales salvo el prompt. Se corre en el servidor."""
import re, sys, collections
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
from shared.object_store import store
def art(rid):
    with connect() as c, c.cursor() as cur:
        cur.execute("select artifact_key from bench_runs where id=%s", (rid,)); k = cur.fetchone()[0]
    return store.get_json(k.removeprefix(store.prefix))['results']
PROMPTS = {'penal-original-v1': [155, 156, 157, 158, 171, 172, 173, 174],
           'tlacua-v1-penas': [159, 160, 161, 162, 175, 176, 177, 178]}
# Pedir el estado, en pregunta («¿en qué estado…?») o en afirmación («se requiere saber en qué estado ocurrieron»,
# «es indispensable conocer el estado», «si me proporcionas el estado…»). Revisado a mano sobre las respuestas.
PIDE = re.compile(r'(?is)¿[^?]{0,200}\b(estado|entidad)\b[^?]{0,200}\?'
                  r'|\ben\s+qu[eé]\s+(estado|entidad)'
                  r'|(saber|conocer|precis\w*|indiqu\w*|indica\w*|proporcion\w*|dime|d[ií]game|compart\w*|se[nñ]al\w*)'
                  r'[^.]{0,60}\b(el|la|tu|su)\s+(estado|entidad)\b')
PENA_CTX = re.compile(r'(?i)\b\d+\s*(a|y)\s*\d+\s*años\s+de\s+prisi[oó]n|\bde\s+\w+\s+a\s+\w+\s+años\s+de\s+prisi[oó]n|d[ií]as\s+multa')
PENA_RESP = re.compile(r'(?i)años\s+de\s+prisi[oó]n|meses\s+de\s+prisi[oó]n|d[ií]as\s+multa|prisi[oó]n\s+de\s+\w+')
for prompt, runs in PROMPTS.items():
    c = collections.Counter()
    for rid in runs:
        for x in art(rid):
            if x.get('error'): continue
            ans, nota = x.get('answer') or '', ((x.get('gate') or {}).get('nota') or '')
            if 'pregunta en qué estado ocurrieron' in nota or 'pregunta dónde ocurrió' in nota or 'pregunta en qué estado' in nota:
                c['debe_pedir'] += 1; c['pidio'] += bool(PIDE.search(ans))
            if 'No vuelvas a preguntar el estado' in nota:
                c['no_debe_pedir'] += 1; c['volvio_a_pedir'] += bool(PIDE.search(ans))
            ctx = ' '.join(ch.get('text') or '' for ch in x.get('chunks') or [])
            if PENA_CTX.search(ctx):
                c['pena_en_ctx'] += 1; c['dio_pena'] += bool(PENA_RESP.search(ans))
            cit = (x.get('citations') or {}).get('counts') or {}
            c['citas'] += sum(v for k, v in cit.items() if k != 'sin_ley')
            c['sin_respaldo'] += cit.get('inexistente', 0) + cit.get('memoria', 0) + cit.get('cruzada', 0)
            c['palabras'] += len(ans.split()); c['respuestas'] += 1
    pct = lambda a, b: f'{c[a]}/{c[b]} ({100 * c[a] / c[b]:.0f} %)' if c[b] else '—'  # noqa: E731
    print(f'{prompt}: pide el estado cuando debe {pct("pidio", "debe_pedir")} · lo vuelve a pedir cuando no debe '
          f'{pct("volvio_a_pedir", "no_debe_pedir")} · da pena si está en el contexto {pct("dio_pena", "pena_en_ctx")} · '
          f'citas sin respaldo {pct("sin_respaldo", "citas")} · palabras por respuesta {c["palabras"] / c["respuestas"]:.0f}')
