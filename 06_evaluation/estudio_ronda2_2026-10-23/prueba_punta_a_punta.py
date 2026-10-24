"""Prueba de punta a punta de ronda2_penal en prod, por HTTP contra la app (127.0.0.1:8060), como lo haría la página.
Abre el estudio solo durante la prueba (no tiene enlaces ni kioscos: nadie más puede entrar), crea 2 códigos de prueba
(la asignación pareja hace que caigan en condiciones distintas), y por cada uno: consentimiento y «Sobre ti», práctica
del tutorial, una situación con una pregunta al asistente, preguntas de comprensión. Revisa en la base la condición, el
prompt (md5) y la configuración guardada en el turno. Al final retira a los dos (borra todo lo suyo) y regresa el estudio
a borrador, pase lo que pase."""
import hashlib, json, re, sys, urllib.request
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from pathlib import Path
from shared.db import connect
from study.store import StudyStore

EID, URL = 'ronda2_penal', 'http://127.0.0.1:8060/api/estudio/p/'
MD5 = {'original': 'f68239bf', 'nuevo': '29af93b7'}
store = StudyStore(connect, Path('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/study/estudios'))

def post(ruta, codigo, cuerpo=None, sse=False):
    req = urllib.request.Request(URL + ruta, json.dumps(cuerpo or {}).encode(),
                                 {'Content-Type': 'application/json', 'X-Codigo': codigo})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            txt = r.read().decode()
            if sse:
                evs = [json.loads(l[6:]) for l in txt.split('\n\n') if l.startswith('data: ')]
                return 200, ''.join(e.get('text', '') for e in evs if e.get('stage') == 'token'), evs
            return 200, json.loads(txt)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or '{}')

def ok(cond, msg):
    print(('  ✔ ' if cond else '  ✘ ') + msg, flush=True)
    return cond

assert store.obtener(EID)['estado'] == 'borrador', 'el estudio no está en borrador: no lo toco'
codigos, fallas = [], 0
try:
    store.cambiar_estado(EID, 'abierto', 'prueba-claude')
    for i, perfil in enumerate([
            {'estudios': 'lic_terminada', 'area': 'sociales', 'carrera': 'Sociología', 'formacion_juridica': 'ninguna',
             'uso_ia': 'semana', 'confianza_basal': 3, 'edad': '25_34'},
            {'estudios': 'prepa', 'area': 'no_aplica', 'formacion_juridica': 'ninguna', 'uso_ia': 'nunca',
             'confianza_basal': 2, 'edad': '45_59'}], 1):
        [cod] = store.crear_codigos(EID, 'participante', 'general', 1, 'PRUEBA punta a punta (Claude, 23-oct): se retira al final', 'prueba-claude')
        codigos.append(cod)
        print(f'Participante de prueba {i}', flush=True)
        st, e = post('estado', cod)
        fallas += not ok(st == 200 and not e['consentido'], 'entra con su código; aún sin consentimiento')
        fallas += not ok('UNAM' not in e.get('consentimiento', '') and 'máximo nivel de estudios' in e.get('consentimiento', ''),
                         'el consentimiento es el de la ronda 2 (sin UNAM, con «máximo nivel de estudios»)')
        fallas += not ok([p['id'] for p in e.get('perfil', [])] == ['estudios', 'area', 'carrera', 'formacion_juridica', 'uso_ia', 'confianza_basal', 'edad'],
                         '«Sobre ti» tiene las preguntas nuevas')
        st, r = post('consentir', cod, {'acepto': True, 'perfil': {'estudios': 'prepa'}})
        fallas += not ok(st == 400 and 'Falta contestar' in r.get('error', ''), 'sin contestar todo, no deja seguir')
        st, e = post('consentir', cod, {'acepto': True, 'perfil': perfil})
        fallas += not ok(st == 200 and e['consentido'] and len(e['escenarios']) == 3, 'acepta; le tocan 3 situaciones')
        st, txt, _ = post('practica_stream', cod, {'mensaje': '¿Qué es una denuncia?'}, sse=True)
        fallas += not ok(st == 200 and len(txt) > 50, f'práctica del tutorial: responde ({len(txt.split())} palabras)')
        post('tutorial_listo', cod)
        esc = e['escenarios'][0]
        st, it = post('iniciar', cod, {'escenario': esc['id']})
        iid = it['intento']['id']
        st, txt, evs = post('preguntar_stream', cod, {'intento': iid, 'mensaje': '¿Lo que me pasó es delito? ¿Qué puedo hacer?'}, sse=True)
        fallas += not ok(st == 200 and evs[-1].get('stage') == 'done' and len(txt) > 50,
                         f'situación «{esc["id"]}»: el asistente responde ({len(txt.split())} palabras, {len(evs[-1].get("fuentes") or [])} fuentes)')
        with connect() as c, c.cursor() as cur:
            cur.execute('SELECT condicion, perfil, consentimiento_md5 FROM estudio_participantes WHERE codigo = %s', (cod,))
            cond, perf, cmd5 = cur.fetchone()
            cur.execute('SELECT t.config, t.sistema_md5, t.respuesta FROM estudio_turnos t JOIN estudio_intentos i ON i.id = t.intento_id '
                        'WHERE i.codigo = %s ORDER BY t.id DESC LIMIT 1', (cod,))
            cfg, smd5, resp = cur.fetchone()
        print(f'  condición: {cond} · prompt md5 {smd5[:8]} · perfil guardado {perf}', flush=True)
        fallas += not ok(smd5[:8] == MD5[cond], f'el turno usó el prompt de su condición ({cond} = {MD5[cond]})')
        fallas += not ok(cfg.get('filtro_estado') is True and cfg.get('rerank') is False and cfg.get('route') is True
                         and cfg.get('descomponer') is True and cfg.get('hyde') is True and cfg.get('k') == 10,
                         'el turno guardó la configuración de la ronda 2 (filtro sí, rerank no, routing, descomponer, HyDE, k 10)')
        fallas += not ok(cmd5 == hashlib.md5(store.spec(EID)['consentimiento'].encode()).hexdigest(), 'guardó la versión del consentimiento')
        st, r = post('a_preguntas', cod, {'intento': iid})
        respuestas = {q['id']: next(iter(q['opciones'])) for q in esc.get('preguntas') or []}
        st, r = post('terminar', cod, {'intento': iid, 'respuestas': respuestas, 'confianza': 3, 'actuaria': 'si', 'detecto': 'no'})
        fallas += not ok(st == 200 and any(x['fin'] for x in r.get('intentos', [])), 'contesta las preguntas de comprensión y termina la situación')
        print('  respuesta (inicio):', re.sub(r'\s+', ' ', resp or '')[:300], flush=True)
finally:
    for cod in codigos:
        store.retirar(cod)
    store.cambiar_estado(EID, 'borrador', 'prueba-claude')
    with connect() as c, c.cursor() as cur:
        cur.execute('SELECT count(*) FROM estudio_participantes WHERE codigo = ANY(%s)', (codigos,))
        quedan = cur.fetchone()[0]
    print(f'Limpieza: {len(codigos)} participantes de prueba retirados (quedan {quedan}); estudio en {store.obtener(EID)["estado"]}', flush=True)
print('FALLAS:', fallas)
