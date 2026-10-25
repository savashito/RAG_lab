"""Puente con la ronda 1 después de prender el rerank en la ronda 2 (versión 12, 25-oct): repite los primeros mensajes
de la ronda 1 con el prompt original (penal-original-v1) + filtro por estado + rerank, 2 repeticiones, igual que
B_filtro (corridas #4 y #5) salvo el rerank. Así «🔁 Ronda 1 real» separa el aporte del filtro (A → B) del aporte del
rerank (B → B_filtro_rerank). Corre en su propio proceso y espera a que termine.
    nohup python lanzar_puente_rerank.py > /tmp/puente_rerank.log 2>&1 &"""
import sys, os, time
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
os.chdir('/home/tlacua/apps/RAG_lab/apps/rewrite_lab')
import main

ids = main.repeticiones.correr({'nombre': 'B_filtro_rerank', 'prompt_tag': 'penal-original-v1', 'repeticiones': 2,
                                'filtro_estado': True, 'rerank': True, 'multiturno': False,
                                'nota': 'puente con la ronda 1 tras prender el rerank en la ronda 2 (v12)'},
                               'rodrigosavagerower@gmail.com (vía Claude)')
print('corridas', ids, flush=True)
time.sleep(5)
while main.repeticiones._running:
    time.sleep(30)
print('terminó', flush=True)
