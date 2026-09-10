"""
rewrite_lab.py — laboratorio de prompts de query rewriting (FastAPI, desplegable).

Pegas un system-prompt y calcula EN VIVO, contra los modelos y la BD:
  * la reescritura de cada pregunta (LLM local, shared.llm_client),
  * el rank del gold chunk con la consulta original, con la reescrita sola, y con
    multi-query (RRF), recuperando el denso desde **pgvector** (no caché local),
  * métricas agregadas (recall@k, MRR) y una tabla coloreada por rank.

Pensado para correr en tlacua.cloud (que alcanza la rtx): configura por env
    LLM_URL   (default http://localhost:41499)   — llama-server
    TEI_URL   (default http://localhost:8085)     — embeddings
    RAG_DB_*  (shared/db.py)                        — Postgres/pgvector
    LEGAL_TABLE (default sistema_penal__qwen06__legal)
    HOST/PORT (default 127.0.0.1:8050; usa HOST=0.0.0.0 para exponerlo)

Local:      uv run python exploracion_datos/rewrite_lab.py
Deploy:     uv run uvicorn exploracion_datos.rewrite_lab:app --host 0.0.0.0 --port 8050
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

HERE = Path(__file__).resolve().parent
LABS = HERE.parent
sys.path.insert(0, str(LABS))

from shared.db import connect
from shared.lexical import rrf
from shared.llm_client import REWRITE_SYSTEM, LlamaClient
from shared.tei_client import TEIClient

GOLDEN = HERE / 'golden_penal.json'
TABLE = os.environ.get('LEGAL_TABLE', 'sistema_penal__qwen06__legal')
Q_INSTRUCT = 'Instruct: Recupera el pasaje del código o la doctrina que responde la pregunta.\nQuery: '
KS = (5, 10, 20)
N_DENSE = 1500   # profundidad del ranking denso que traemos de pgvector para calcular el rank

golden = json.load(open(GOLDEN))
tei = TEIClient()          # embebe en vivo (sin caché); TEI_URL por env
llm = LlamaClient()        # LLM_URL por env, modelo auto-detectado


def gold_ids_for(answer: str) -> set[int]:
    with connect() as c, c.cursor() as cur:
        cur.execute(f"SELECT id FROM {TABLE} WHERE text LIKE %s", (f'%{answer}%',))
        return {r[0] for r in cur.fetchall()}


def dense_ids(qvec) -> list[int]:
    with connect() as c, c.cursor() as cur:
        cur.execute(f"SELECT id FROM {TABLE} ORDER BY embedding <=> %s LIMIT %s", (qvec, N_DENSE))
        return [r[0] for r in cur.fetchall()]


def rank_in(ids, gid) -> int | None:
    for r, j in enumerate(ids, 1):
        if j in gid:
            return r
    return None


print(f'Cargando: tabla {TABLE} · {len(golden)} preguntas · LLM {llm.model}')
gold_ids = [gold_ids_for(g['answer']) for g in golden]
orig_qvecs = tei.embed([Q_INSTRUCT + g['q'] for g in golden], use_cache=False)
orig_ids = [dense_ids(orig_qvecs[i]) for i in range(len(golden))]
orig_rank = [rank_in(orig_ids[i], gold_ids[i]) for i in range(len(golden))]
missing = [i for i in range(len(golden)) if not gold_ids[i]]
if missing:
    print(f'  aviso: {len(missing)} preguntas sin gold chunk en la tabla (ancla no hallada): {missing}')
print('Listo.')


def subset_indices(kind):
    if kind == 'hard':
        return [i for i, g in enumerate(golden) if g['difficulty'] in ('hard', 'very_hard')]
    if kind == 'muestra':
        return [12, 14, 11, 4, 15, 19]
    return list(range(len(golden)))


def metrics(ranks):
    n = len(ranks) or 1
    out = {f'recall@{k}': round(sum(1 for r in ranks if r and r <= k) / n, 3) for k in KS}
    out['MRR'] = round(sum(1.0 / r for r in ranks if r) / n, 3)
    return out


def eval_prompt(system_prompt, kind):
    idx = subset_indices(kind)
    t0 = time.time()
    rewrites = [llm.chat(system_prompt, golden[i]['q']) for i in idx]   # llama-server secuencial
    rw_vecs = tei.embed([Q_INSTRUCT + r for r in rewrites], use_cache=False)
    rows, r_orig, r_rw, r_mq = [], [], [], []
    for k, i in enumerate(idx):
        rw_ids = dense_ids(rw_vecs[k])
        mq_ids = rrf([orig_ids[i], rw_ids])
        ro, rr, rm = orig_rank[i], rank_in(rw_ids, gold_ids[i]), rank_in(mq_ids, gold_ids[i])
        r_orig.append(ro); r_rw.append(rr); r_mq.append(rm)
        rows.append({'idx': i, 'difficulty': golden[i]['difficulty'], 'type': golden[i]['type'],
                     'question': golden[i]['q'], 'rewrite': rewrites[k],
                     'rank_orig': ro, 'rank_rewrite': rr, 'rank_mq': rm})
    return {'rows': rows, 'n': len(idx), 'seconds': round(time.time() - t0, 1),
            'agg': {'denso (orig)': metrics(r_orig), 'rewrite-solo': metrics(r_rw), 'multi-query': metrics(r_mq)}}


HTML = """<!doctype html><html lang=es><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Rewrite Lab</title>
<style>
 :root{color-scheme:light dark}
 body{font:14px/1.5 system-ui,sans-serif;margin:0;background:#0f1115;color:#e6e6e6}
 header{padding:14px 20px;background:#171a21;border-bottom:1px solid #2a2f3a}
 h1{font-size:16px;margin:0}
 .wrap{max-width:1200px;margin:0 auto;padding:20px}
 textarea{width:100%;min-height:190px;background:#0b0d12;color:#e6e6e6;border:1px solid #2a2f3a;
   border-radius:8px;padding:12px;font:13px/1.5 ui-monospace,monospace;box-sizing:border-box}
 .row{display:flex;gap:12px;align-items:center;margin:12px 0;flex-wrap:wrap}
 button{background:#3b82f6;color:#fff;border:0;border-radius:8px;padding:9px 18px;font-weight:600;cursor:pointer}
 button:disabled{opacity:.5;cursor:default}
 select{background:#0b0d12;color:#e6e6e6;border:1px solid #2a2f3a;border-radius:8px;padding:8px}
 table{border-collapse:collapse;width:100%;margin-top:14px;font-size:13px}
 th,td{border:1px solid #2a2f3a;padding:6px 8px;text-align:left;vertical-align:top}
 th{background:#171a21;position:sticky;top:0}
 td.r{text-align:center;font-weight:700;width:52px}
 .cards{display:flex;gap:12px;flex-wrap:wrap;margin-top:6px}
 .card{background:#171a21;border:1px solid #2a2f3a;border-radius:10px;padding:12px 16px;min-width:180px}
 .card h3{margin:0 0 6px;font-size:13px;color:#9aa4b2}
 .m{display:flex;justify-content:space-between;gap:16px}
 .muted{color:#9aa4b2}.rw{color:#a5d6ff}.spin{display:none}
</style>
<header><h1>\U0001f9ea Rewrite Lab — prompts de query rewriting (modelos locales + pgvector)</h1></header>
<div class=wrap>
 <p class=muted>Pega un <b>system prompt</b>, elige el set y corre. Rank del gold chunk:
 <b>orig</b> (consulta original), <b>rw</b> (reescritura sola), <b>mq</b> (multi-query RRF).
 Verde=arriba, rojo=hundido. Denso desde pgvector.</p>
 <textarea id=prompt></textarea>
 <div class=row>
   <label>Set: <select id=subset>
     <option value=hard>hard + very_hard</option>
     <option value=muestra>muestra rápida (6)</option>
     <option value=todas>todas (34)</option>
   </select></label>
   <button id=run onclick=run()>▶ Correr</button>
   <span class=spin id=spin>⏳ reescribiendo con el LLM… (~1-2s por pregunta)</span>
 </div>
 <div id=cards class=cards></div>
 <div id=out></div>
</div>
<script>
const DEFAULT=%DEFAULT%;
document.getElementById('prompt').value=DEFAULT;
function color(r){ if(r==null) return '#7f1d1d'; if(r<=5) return '#166534'; if(r<=20) return '#3f6212';
  if(r<=100) return '#854d0e'; return '#7f1d1d'; }
function cell(r){ return `<td class=r style="background:${color(r)}">${r==null?'∞':r}</td>`; }
async function run(){
  const b=document.getElementById('run'), s=document.getElementById('spin');
  b.disabled=true; s.style.display='inline'; document.getElementById('out').innerHTML='';
  document.getElementById('cards').innerHTML='';
  try{
    const res=await fetch('/run',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({prompt:document.getElementById('prompt').value, subset:document.getElementById('subset').value})});
    const d=await res.json();
    if(d.error){ document.getElementById('out').innerHTML='<p style=color:#f87171>Error: '+d.error+'</p>'; return; }
    const order=['denso (orig)','rewrite-solo','multi-query'];
    document.getElementById('cards').innerHTML=order.map(name=>{
      const m=d.agg[name]; return `<div class=card><h3>${name}</h3>`+
        Object.entries(m).map(([k,v])=>`<div class=m><span class=muted>${k}</span><b>${v}</b></div>`).join('')+`</div>`;
    }).join('')+`<div class=card><h3>info</h3><div class=m><span class=muted>preguntas</span><b>${d.n}</b></div>
      <div class=m><span class=muted>tiempo</span><b>${d.seconds}s</b></div></div>`;
    let h='<table><tr><th>#</th><th>dif</th><th>orig</th><th>rw</th><th>mq</th><th>pregunta → reescritura</th></tr>';
    for(const r of d.rows){ h+=`<tr><td>${r.idx}</td><td>${r.difficulty}</td>`+
      cell(r.rank_orig)+cell(r.rank_rewrite)+cell(r.rank_mq)+
      `<td>${r.question}<br><span class=rw>↳ ${r.rewrite}</span></td></tr>`; }
    document.getElementById('out').innerHTML=h+'</table>';
  }catch(e){ document.getElementById('out').innerHTML='<p style=color:#f87171>'+e+'</p>'; }
  finally{ b.disabled=false; s.style.display='none'; }
}
</script></html>"""


app = FastAPI(title='Rewrite Lab')


@app.get('/', response_class=HTMLResponse)
def index():
    return HTML.replace('%DEFAULT%', json.dumps(REWRITE_SYSTEM))


@app.post('/run')
async def run(req: Request):
    body = await req.json()
    try:
        return JSONResponse(eval_prompt(body.get('prompt') or REWRITE_SYSTEM, body.get('subset', 'hard')))
    except Exception as e:
        return JSONResponse({'error': f'{type(e).__name__}: {e}'})


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', 8050)))
