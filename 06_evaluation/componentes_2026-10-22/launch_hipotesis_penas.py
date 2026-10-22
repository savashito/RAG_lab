"""¿Por qué tlacua-v1-penas cita menos artículos en el set 14? Observación (hipotesis_penas en el informe): las respuestas
que fallan casi nunca citan ningún artículo, y casi nunca tienen sección «Fundamento jurídico» (penal-original-v1 la
exige y la trae siempre). Prueba causal, set 14, configuración de la ronda 1 (con routing) + filtro v3 + por delito (+3) + remisiones:
  a) tlacua-v1-penas tal cual (control)
  b) a + sección obligatoria «Fundamento jurídico»                          → prueba la hipótesis
  c) b + no preguntar el estado si ya está determinado o si se comparan     → prueba la otra falla (pedir el estado de más)
2 repeticiones. Espera a que terminen las pruebas por componente (/tmp/prueba_juez.log con FIN). Arranca la copia
temporal de prod en 8099 y la apaga al final."""
import json, os, subprocess, sys, time, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
def q(sql, args=()):
    with connect() as c, c.cursor() as cur:
        cur.execute(sql, args); return cur.fetchall()
while subprocess.run(['grep', '-q', '^FIN', '/tmp/prueba_juez.log']).returncode != 0:
    time.sleep(60)
(base,), = q("SELECT text FROM bench_prompt_tags WHERE tag = 'tlacua-v1-penas'")
FUNDAMENTO = ('\n\n8. Fundamento jurídico. Termina SIEMPRE con un apartado titulado «Fundamento jurídico» que liste cada norma '
              'del CONTEXTO en la que te apoyaste: nombre completo del ordenamiento, número de artículo y fracción. Cita '
              'esos mismos números de artículo en el cuerpo de la respuesta.')
NO_PREGUNTAR = ('\n\n9. Estado. Si el sistema ya determinó el estado de los hechos, o la persona pide comparar varios '
                'estados, NO le preguntes en qué estado ocurrieron los hechos ni le pidas elegir uno: responde para cada '
                'estado que mencionó.')
prompts = {'a control': base, 'b + Fundamento jurídico': base + FUNDAMENTO, 'c + Fundamento + no preguntar estado': base + FUNDAMENTO + NO_PREGUNTAR}
subprocess.run('rm -rf /tmp/rltest && rsync -a --exclude .venv --exclude .git ~/apps/RAG_lab/ /tmp/rltest/', shell=True, check=True)
subprocess.Popen(['/home/tlacua/apps/RAG_lab/.venv/bin/uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8099'],
                 cwd='/tmp/rltest/apps/rewrite_lab', env=dict(os.environ, GOOGLE_CLIENT_ID=''),
                 stdout=open('/tmp/rltest_app_h.log', 'w'), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                 start_new_session=True)
for _ in range(100):
    try:
        urllib.request.urlopen('http://127.0.0.1:8099/healthz', timeout=5); break
    except Exception:  # noqa: BLE001
        time.sleep(3)
# Configuración de la ronda 2 = la de la ronda 1 (piloto_penal_v7_final.yaml: híbrido, k 10, HyDE, descomponer y
# routing por código) + filtro v3 + por delito + remisiones (como D).
cfg = {'setting': 'híbrido', 'k': 10, 'neighbors': True, 'hyde': True, 'rerank': False, 'decompose': True, 'route': True,
       'jurisdictions': [], 'gate': True, 'crimes': True, 'crime_extra_k': 3, 'remisiones': True}
try:
    for rep in (1, 2):
        for nombre, texto in prompts.items():
            body = dict(cfg, system=texto, set_id=14, label=f'hipotesis-penas-2026-10-22 · D·v3 + routing {nombre} · rep {rep}')
            while q("select id from bench_runs where status='running'"):
                time.sleep(20)
            req = urllib.request.Request('http://127.0.0.1:8099/api/bench/run', json.dumps(body).encode(),
                                         {'Content-Type': 'application/json'})
            rid = json.load(urllib.request.urlopen(req, timeout=60))['run_id']
            time.sleep(10)
            while q("select status from bench_runs where id=%s", (rid,))[0][0] == 'running':
                time.sleep(20)
            print(rid, body['label'], q("select status, done, n, metrics->>'score' from bench_runs where id=%s", (rid,))[0], flush=True)
finally:
    subprocess.run(['pkill', '-f', '[u]vicorn main:app --host 127.0.0.1 --port 8099'])
    print('copia temporal apagada', flush=True)
print('FIN', flush=True)
