"""Prueba de punta a punta de filtro_ve_pregunta en ronda2_penal (abierto): 2 participantes de prueba (uno por condición)
hacen la conversación del usuario: «mande fotos intimas a alguien y ahora quiere dinero, que hago?» → «Queretaro».
Revisa en el 2.º mensaje: que el turno guardó filtro_ve_pregunta, qué decidió el filtro (recalculado con el mismo texto),
si el asistente vuelve a pedir el estado y si nombra el Código Penal de Querétaro. Retira a los dos al final."""
import json, sys, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from pathlib import Path
from shared.db import connect
from study.store import StudyStore
from study.analisis import analizar_respuesta
import jurisdiction_gate as jg
EID, URL = 'ronda2_penal', 'http://127.0.0.1:8060/api/estudio/p/'
store = StudyStore(connect, Path('/nonexistent'))
def post(ruta, cod, cuerpo=None, sse=False):
    req = urllib.request.Request(URL + ruta, json.dumps(cuerpo or {}).encode(), {'Content-Type': 'application/json', 'X-Codigo': cod})
    with urllib.request.urlopen(req, timeout=300) as r:
        t = r.read().decode()
        return ''.join(json.loads(l[6:]).get('text', '') for l in t.split('\n\n') if l.startswith('data: ') and '"token"' in l) if sse else json.loads(t)
assert store.obtener(EID)['estado'] == 'abierto'
codigos = []
try:
    for i in range(2):
        [cod] = store.crear_codigos(EID, 'participante', 'general', 1, 'PRUEBA respuesta corta (Claude, 25-oct): se retira al final', 'prueba-claude')
        codigos.append(cod)
        e = post('consentir', cod, {'acepto': True, 'perfil': {'estudios': 'prepa', 'formacion_juridica': 'ninguna', 'uso_ia': 'nunca',
                                                               'confianza_basal': 2, 'edad': '25_34'}})
        post('tutorial_listo', cod)
        it = post('iniciar', cod, {'escenario': 'fotos'})['intento']['id']
        post('preguntar_stream', cod, {'intento': it, 'mensaje': 'mande fotos intimas a alguien y ahora quiere dinero, que hago?'}, sse=True)
        r2 = post('preguntar_stream', cod, {'intento': it, 'mensaje': 'Queretaro'}, sse=True)
        with connect() as c, c.cursor() as cur:
            cur.execute('SELECT condicion FROM estudio_participantes WHERE codigo = %s', (cod,)); cond = cur.fetchone()[0]
            cur.execute('SELECT n, pregunta, respuesta, config FROM estudio_turnos WHERE intento_id = %s ORDER BY n', (it,)); ts = cur.fetchall()
        msgs = []
        for n, p, r, cfg in ts:
            msgs += [{'role': 'user', 'content': p}, {'role': 'assistant', 'content': r}]
        texto, persona = jg.texto_para_filtro(msgs[:-1], con_pregunta=True)
        import main as _m  # noqa: F401  (para gate_for con el mismo corpus)
        g = _m.gate_for(texto, 'derecho_penal_mexicano', sistema=jg.EXTRAER_SYSTEM_V2, texto_regex=persona)
        a = analizar_respuesta(ts[1][2], [])
        print(f'== participante {i + 1} · condición {cond} · turno 2 guardó filtro_ve_pregunta={ts[1][3].get("filtro_ve_pregunta")}')
        print('   frase del asistente que vio el filtro:', jg.pregunta_de_lugar(ts[0][2]))
        print('   el filtro decidió: estados de los hechos', g.get('estados'), '· otros', g.get('otros'))
        print('   ¿vuelve a pedir el estado?', a['pide_lugar_estricto'], '· ¿nombra el Código Penal de Querétaro?',
              'código penal del estado de querétaro' in (ts[1][2] or '').lower() or 'código penal de querétaro' in (ts[1][2] or '').lower())
        print('   inicio de la respuesta:', ' '.join((ts[1][2] or '').split())[:260])
finally:
    for cod in codigos:
        store.retirar(cod)
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM estudio_participantes p JOIN estudio_codigos k USING (codigo) WHERE k.estudio = %s", (EID,))
        print('Limpieza: participantes de prueba retirados; quedan en la ronda 2:', cur.fetchone()[0])
