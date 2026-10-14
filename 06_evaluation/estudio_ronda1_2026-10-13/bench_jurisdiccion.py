"""Benchmark automático de JURISDICCIÓN (sin juez, sin personas).

Preguntas: la PRIMERA pregunta real de cada participante en cada situación (ronda 1). Cada una se corre:
  · tal cual (con o sin lugar, como la escribió la persona) y
  · si no decía el lugar, también con «Esto pasó en <estado de la situación>.» al final.
Con cada prompt (A actual, C sencillo+contexto, y los que se agreguen), una sola vuelta, misma configuración
del estudio. Mide, sin juez: ¿cita códigos de OTRO estado?, ¿pregunta el lugar?, ¿cita el código correcto?,
y si los otros estados venían en el CONTEXTO recuperado (búsqueda) o no (modelo).
Uso: python bench_jurisdiccion.py <salida.json> <prompt_id>=<archivo|ACTUAL> ..."""
import sys, json, time, urllib.request, concurrent.futures as cf
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
from shared.code_routes import codes_in, short_label
from study.analisis import lugares_mencionados, LUGARES, _PIDE_LUGAR
from shared.code_routes import fold
API = 'http://127.0.0.1:8099/chat'
PRUEBAS = ['NGSX-GGPH', 'K9TQ-6P86', 'FYJ2-VS7R']
ESTADO = {('mensajes_trabajo', 'qro'): 'Querétaro', ('mensajes_trabajo', 'cdmx'): 'CDMX', ('fotos', None): 'Querétaro', ('citatorio', None): 'Querétaro'}
NOMBRE = {'Querétaro': 'Querétaro', 'CDMX': 'la Ciudad de México'}
GOLD_LEY = {'mensajes_trabajo': None, 'fotos': {'LGExtorsión', 'Querétaro'}, 'citatorio': {'Querétaro', 'CNPP'}}
out_path = sys.argv[1]
PROMPTS = {}
for a in sys.argv[2:]:
    pid, f = a.split('=', 1); PROMPTS[pid] = '' if f == 'ACTUAL' else open(f).read().strip()
with connect() as c, c.cursor() as cur:
    cur.execute("""select t.pregunta, i.escenario, i.variante from estudio_turnos t join estudio_intentos i on i.id=t.intento_id
                   where t.n=1 and i.codigo <> all(%s) order by t.id""", (PRUEBAS,))
    base = cur.fetchall()
casos = []
for q, esc, var in base:
    est = ESTADO[(esc, var)]
    tiene = bool(lugares_mencionados(q))
    casos.append(dict(esc=esc, var=var, estado=est, version='original', dice_lugar=tiene, pregunta=q))
    if not tiene:
        casos.append(dict(esc=esc, var=var, estado=est, version='con_lugar_agregado', dice_lugar=True, pregunta=q.rstrip() + f' Esto pasó en {NOMBRE[est]}.'))
CFG = {'setting': 'híbrido', 'k': 10, 'neighbors': True, 'hyde': True, 'decompose': True, 'route': True, 'topic': 'derecho_penal_mexicano'}
def correr(caso, pid):
    body = dict(CFG, messages=[{'role': 'user', 'content': caso['pregunta']}], system=PROMPTS[pid])
    for intento in range(3):
        try:
            req = urllib.request.Request(API, json.dumps(body).encode(), {'Content-Type': 'application/json'})
            r = json.load(urllib.request.urlopen(req, timeout=300))
            if r.get('error'): raise RuntimeError(r['error'])
            break
        except Exception as e:
            err = str(e); time.sleep(5)
    else:
        return dict(caso, prompt=pid, error=err)
    ans = r.get('answer') or ''
    permitidos = {caso['estado']} | ({'CDMX'} if caso['esc'] == 'citatorio' else set())   # en el citatorio, decir «no aplica el de la CDMX» es correcto
    resp = [h['label'] for h in codes_in(ans)]
    ctx = sorted({short_label(ch.get('source') or '') for ch in r.get('chunks') or []} & LUGARES)
    otros = sorted(set(l for l in resp if l in LUGARES) - permitidos)
    return dict(caso, prompt=pid, palabras=len(ans.split()), pide_lugar=bool(_PIDE_LUGAR.search(fold(ans))),
                cita_estado_correcto=caso['estado'] in resp, otros_estados=otros, otros_en_contexto=sorted(set(ctx) - permitidos),
                primera_ley=resp[0] if resp else None, respuesta=ans[:1500], segundos=r.get('seconds'))
res = []
with cf.ThreadPoolExecutor(3) as ex:
    futs = [ex.submit(correr, caso, pid) for pid in PROMPTS for caso in casos]
    for k, f in enumerate(cf.as_completed(futs), 1):
        res.append(f.result())
        if k % 20 == 0: print(k, '/', len(futs), flush=True); json.dump(res, open(out_path, 'w'), ensure_ascii=False)
json.dump(res, open(out_path, 'w'), ensure_ascii=False)
def m(xs): return round(sum(xs) / len(xs), 3) if xs else None
for pid in PROMPTS:
    for etiqueta, filtro in (('dice lugar (original)', lambda r: r['version'] == 'original' and r['dice_lugar']),
                             ('NO dice lugar (original)', lambda r: r['version'] == 'original' and not r['dice_lugar']),
                             ('lugar agregado', lambda r: r['version'] == 'con_lugar_agregado')):
        rs = [r for r in res if r['prompt'] == pid and filtro(r) and 'error' not in r]
        print(f"{pid:10} {etiqueta:26} n={len(rs):3} · cita otro estado {m([bool(r['otros_estados']) for r in rs])} "
              f"(de esos, venían en el contexto {m([set(r['otros_estados']) <= set(r['otros_en_contexto']) for r in rs if r['otros_estados']])}) "
              f"· pide lugar {m([r['pide_lugar'] for r in rs])} · cita el estado correcto {m([r['cita_estado_correcto'] for r in rs])} · palabras {m([r['palabras'] for r in rs])}")
print('errores:', sum('error' in r for r in res), '· FIN')
