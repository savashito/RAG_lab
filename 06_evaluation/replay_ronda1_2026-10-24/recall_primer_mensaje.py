"""Referencia para «💬 Reescritura multiturno · recall»: el recall de los PRIMEROS mensajes reales de la ronda 1 (sin
historial, no hay nada que reescribir), con las mismas dos configuraciones: solo HyDE, y filtro + descomponer + HyDE +
rerank. Mismos artículos esperados (los de cada situación). Imprime solo agregados.   python recall_primer_mensaje.py"""
import sys, os, time, statistics as st
from collections import defaultdict
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
os.chdir('/home/tlacua/apps/RAG_lab/apps/rewrite_lab')
import main
from study.validar import escenario_efectivo
CONFIG = {'solo HyDE': (False, False, False), 'filtro + descomponer + HyDE + rerank': (True, True, True)}
d = main.study_store.export('piloto_penal'); spec = main.study_store.spec('piloto_penal')
por_id = {e['id']: e for e in spec['escenarios']}; intento = {i['id']: i for i in d['intentos']}
gold = {}
tot = defaultdict(lambda: [0, 0]); seg = defaultdict(list)
with main.connect() as c, c.cursor() as cur:
    for t in d['turnos']:
        if t['n'] != 1:
            continue
        i = intento[t['intento_id']]; k = (i['escenario'], i['variante'])
        if k not in gold:
            ef = escenario_efectivo(por_id[i['escenario']], i['variante'])
            gold[k] = [g for g in main._study_resolver([g for x in ef.get('gold') or [] for g in main._study_gold_refs(x)]) if any(x.get('ids') for x in g)]
        sit = f"situación {i['escenario']}{' ' + i['variante'] if i['variante'] else ''}"
        for nombre, (filtro, desc, rr) in CONFIG.items():
            t0 = time.time()
            jur = main.gate_for(t['pregunta'], 'derecho_penal_mexicano')['jurisdictions'] if filtro else None
            scored, _, _ = main.retrieve_ranked(cur, t['pregunta'], 'híbrido', 'derecho_penal_mexicano', jur, True, True, rr, desc)
            seg[nombre].append(time.time() - t0)
            chk = main.retrieval_check(gold[k], [cid for cid, _ in scored][:50])
            h = sum(1 for g in chk['groups'] if g['rank'] and g['rank'] <= 10)
            for clave in ('todas', sit):
                tot[(nombre, clave)][0] += h; tot[(nombre, clave)][1] += len(gold[k])
for nombre in CONFIG:
    print(f'== {nombre} · {st.mean(seg[nombre]):.1f} s por mensaje')
    for (n, clave), (h, g) in sorted(tot.items()):
        if n == nombre:
            print(f'   {clave}: {100 * h / g:.1f} % ({h} de {g})')
