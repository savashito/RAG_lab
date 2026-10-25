"""Set de referencia «¿Tlacua le pidió el lugar a la persona?»: Gemma etiqueta cada respuesta guardada del asistente
(las repeticiones con filtro de 🔁 Ronda 1 real, todos los mensajes, y los benchmarks #211–#242) y se guarda en la tabla
pide_lugar_etiquetas (en la base, no en el repo: las respuestas pueden repetir detalles que contaron participantes).
Sirve para comparar versiones de jurisdiction_gate.pregunta_de_lugar sin volver a llamar a Gemma (comparar.py).
Retoma donde se quedó: no vuelve a etiquetar respuestas ya etiquetadas con el mismo prompt.   python etiquetar.py"""
import sys, os, hashlib
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
os.chdir('/home/tlacua/apps/RAG_lab/apps/rewrite_lab')
import main
import jurisdiction_gate as jg
from shared.object_store import store

SISTEMA = ('Lees la respuesta de un asistente jurídico a una persona. ¿Al final de la respuesta, o en algún lugar, el asistente '
           'le PIDE a la persona que diga dónde ocurrieron los hechos (el estado, la ciudad o el lugar)? Cuenta preguntas («¿en qué '
           'estado pasó?») y peticiones («indícame dónde ocurrió»). No cuenta si solo explica que la ley depende del estado sin '
           'pedirlo. Devuelve SOLO JSON: {"pide_lugar": true|false, "frase": "<la frase exacta con la que lo pide, o vacío>"}')
PROMPT_MD5 = hashlib.md5(SISTEMA.encode()).hexdigest()
with main.connect() as c, c.cursor() as cur:
    cur.execute("""CREATE TABLE IF NOT EXISTS pide_lugar_etiquetas (
        id serial PRIMARY KEY, respuesta_md5 text NOT NULL, respuesta text NOT NULL, fuente text, gemma_pide boolean,
        gemma_frase text, gemma_raw text, prompt_md5 text NOT NULL, modelo text, creado timestamptz DEFAULT now(),
        UNIQUE (respuesta_md5, prompt_md5))""")
    c.commit()
    cur.execute("""SELECT t->>'respuesta', 'ronda 1 real · ' || r.nombre || ' · rep ' || r.repeticion FROM rep_conversaciones v
                   JOIN rep_corridas r ON r.id = v.corrida_id, jsonb_array_elements(v.turnos) t
                   WHERE (r.config->>'filtro_estado')::bool ORDER BY v.id""")
    respuestas = [(r, f) for r, f in cur.fetchall() if r]
    cur.execute("SELECT id, artifact_key FROM bench_runs WHERE id BETWEEN 211 AND 242 AND artifact_key IS NOT NULL ORDER BY id")
    for rid, k in cur.fetchall():
        for x in store.get_json(k.removeprefix(store.prefix))['results']:
            if x.get('answer'):
                respuestas.append((x['answer'], f'benchmark #{rid}'))
    cur.execute('SELECT respuesta_md5 FROM pide_lugar_etiquetas WHERE prompt_md5 = %s', (PROMPT_MD5,))
    hechas = {r[0] for r in cur.fetchall()}
nuevas = 0
for r, fuente in respuestas:
    m = hashlib.md5(r.encode()).hexdigest()
    if m in hechas:
        continue
    try:
        raw = main.llm.chat(SISTEMA, r, temperature=0.0, max_tokens=200, timeout=60)
    except Exception as e:  # noqa: BLE001
        raw = f'error: {type(e).__name__}: {e}'
    d = jg._json(raw) or {}
    with main.connect() as c, c.cursor() as cur:
        cur.execute("INSERT INTO pide_lugar_etiquetas (respuesta_md5, respuesta, fuente, gemma_pide, gemma_frase, gemma_raw, prompt_md5, modelo) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (m, r, fuente, d.get('pide_lugar') if isinstance(d.get('pide_lugar'), bool) else None, d.get('frase'), raw[:2000],
                     PROMPT_MD5, os.environ.get('LLM_MODEL', 'Gemma-4-4B-8b')))
        c.commit()
    hechas.add(m); nuevas += 1
print(f'{len(respuestas)} respuestas · {nuevas} etiquetadas ahora · {len(hechas)} en el set', flush=True)
