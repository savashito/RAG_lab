"""Estudio con usuarios (apps/rewrite_lab/study/).

Las pruebas de cálculos y validación no necesitan nada. Las del store y la API necesitan un
Postgres DESECHABLE: `ESTUDIO_TEST_DSN=postgresql://test@127.0.0.1:55432/estudio_test`. Borran las
tablas estudio_* al empezar, así que nunca apuntes esa variable a la BD de prod.
"""
from __future__ import annotations

import json as _json
import os
import random
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / 'apps' / 'rewrite_lab'
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP.parents[1]))   # shared/

from study import analisis as A  # noqa: E402
from study.validar import validar, vista_publica  # noqa: E402

SEED = APP / 'study' / 'estudios' / 'piloto_penal.yaml'

SPEC_YAML = """
id: prueba
titulo: Prueba
consentimiento: ok
asistente: {tema: t, max_turnos: 2}
escenarios_por_persona: 2
tutorial: {texto: 'Así funciona', ejemplo: '¿Qué es la legítima defensa?', max_preguntas: 2}
fase: principal
condiciones:
  - {id: actual}
  - {id: sencillo, sistema: 'Habla sencillo'}
ultima_situacion:
  - {id: estado, texto: '¿De qué estado?', opciones: {qro: Qro, cdmx: CDMX}}
perfil:
  - {id: formacion, pregunta: '¿Formación?', opciones: {ninguna: 'No', estudiante: 'Sí'}}
  - {id: carrera, tipo: texto, pregunta: '¿Carrera?'}
  - {id: confianza, tipo: escala, pregunta: '¿Confianza?', obligatorio: false}
escenarios:
  - id: a
    titulo: A
    texto: texto A
    referencia: ref A
    gold: [Cita el art. 179 del Código Penal de la Ciudad de México]
    preguntas: [{id: p1, texto: '¿Pregunta?', opciones: {si: Sí, no: 'No'}, correcta: si}]
  - id: b
    titulo: B
    texto: texto B
    referencia: ref B
    preguntas: [{id: p1, texto: '¿Pregunta?', opciones: {si: Sí, no: 'No', otra: No está mi respuesta}, correcta: 'no'}]
  - id: c
    titulo: C
    texto: base
    referencia: base
    preguntas: [{id: p1, texto: '¿Pregunta?', opciones: {si: Sí, no: 'No'}, correcta: si}]
    variantes:
      - {id: v1, texto: texto C1, referencia: ref C1}
      - {id: v2, texto: texto C2, referencia: ref C2, correctas: {p1: no}}
"""


# ── validación ───────────────────────────────────────────────────────────────
def test_seed_es_valido():
    from bench import gold_refs
    assert validar(SEED.read_text(), lambda t: gold_refs('', [{'kind': 'must', 'text': t}])) == []


def test_validar_detecta_errores():
    malo = SPEC_YAML.replace('correcta: si}]\n  - id: b', 'correcta: tal_vez}]\n  - id: b').replace('id: c', 'id: a')
    errs = validar(malo)
    assert any('«correcta»' in e for e in errs)
    assert any('id repetido' in e for e in errs)
    assert any('gold' in e for e in validar(SPEC_YAML, gold_refs=lambda t: []))


def test_ronda2_es_valido():
    from bench import gold_refs
    ronda2 = SEED.parent / 'ronda2_penal.yaml'
    assert validar(ronda2.read_text(), lambda t: gold_refs('', [{'kind': 'must', 'text': t}])) == []


def test_perfil_mostrar_si():
    from study.validar import cargar, limpiar_perfil
    spec, _ = cargar(SPEC_YAML)
    spec['perfil'] = [
        {'id': 'estudios', 'pregunta': 'Nivel', 'opciones': {'prepa': 'Prepa', 'lic': 'Licenciatura'}},
        {'id': 'area', 'pregunta': 'Área', 'opciones': {'derecho': 'Derecho', 'otra': 'Otra'}, 'mostrar_si': {'estudios': ['lic']}},
        {'id': 'edad', 'pregunta': 'Edad', 'opciones': {'18_24': '18–24'}}]
    # Sin estudios universitarios: «área» no se pide, y si llega no se guarda.
    assert limpiar_perfil(spec, {'estudios': 'prepa', 'edad': '18_24', 'area': 'derecho'}) == ({'estudios': 'prepa', 'edad': '18_24'}, [])
    # Con licenciatura: «área» es obligatoria.
    assert limpiar_perfil(spec, {'estudios': 'lic', 'edad': '18_24'})[1] == ['Área']
    assert limpiar_perfil(spec, {'estudios': 'lic', 'edad': '18_24', 'area': 'otra'})[0]['area'] == 'otra'
    assert vista_publica(spec, [])['perfil'][1]['mostrar_si'] == {'estudios': ['lic']}
    # Errores: apuntar a una pregunta posterior o a un valor que no existe.
    import yaml
    for malo, texto in (({'edad': ['18_24']}, 'anterior'), ({'estudios': ['doctorado']}, 'lista de opciones')):
        spec['perfil'][1]['mostrar_si'] = malo
        assert any(texto in e for e in validar(yaml.safe_dump(spec, allow_unicode=True))), malo


def test_variantes():
    import yaml
    from study.validar import escenario_efectivo, limpiar_perfil
    spec = yaml.safe_load(SPEC_YAML)
    c = spec['escenarios'][2]
    assert escenario_efectivo(c, 'v2')['texto'] == 'texto C2'
    from study.validar import cargar
    c = cargar(SPEC_YAML)[0]['escenarios'][2]
    assert escenario_efectivo(c, 'v2')['preguntas'][0]['correcta'] == 'no'
    assert escenario_efectivo(c, 'v1')['preguntas'][0]['correcta'] == 'si'
    assert escenario_efectivo(c, None)['texto'] == 'base'
    v = vista_publica(cargar(SPEC_YAML)[0], ['c'], {'c': 'v2'})
    assert v['escenarios'][0]['texto'] == 'texto C2' and 'v1' not in repr(v) and 'ref C' not in repr(v)
    assert validar(SPEC_YAML.replace('correctas: {p1: no}', 'correctas: {zz: no}'))
    perfil, faltan = limpiar_perfil(cargar(SPEC_YAML)[0], {'formacion': 'x', 'confianza': 9})
    assert perfil == {} and len(faltan) == 2                         # confianza no es obligatoria


def test_asignar_variante():
    assert A.asignar_variante(['qro', 'cdmx'], {'qro': 3, 'cdmx': 2}) == 'cdmx'


def test_vista_publica_no_filtra_respuestas():
    import yaml
    v = vista_publica(yaml.safe_load(SPEC_YAML), ['b', 'a'])
    assert [e['id'] for e in v['escenarios']] == ['b', 'a']
    plano = repr(v)
    assert 'correcta' not in plano and 'ref A' not in plano and 'gold' not in plano and '179' not in plano


# ── cálculos ─────────────────────────────────────────────────────────────────
def test_asignar_balancea():
    conteos = {'a': 3, 'b': 0, 'c': 1}
    assert sorted(A.asignar(['a', 'b', 'c'], conteos, 2, random.Random(1))) == ['b', 'c']


def test_puntuar_comprension():
    esc = {'preguntas': [{'id': 'x', 'correcta': 'si'}, {'id': 'y', 'correcta': 'no'}, {'id': 'z', 'correcta': 'a'}]}
    r = A.puntuar_comprension(esc, {'x': 'si', 'y': 'si', 'z': 'no_se'})
    assert (r['aciertos'], r['total'], r['no_se']) == (1, 3, 1)


def test_rango_y_recall():
    grupos = [[{'ids': [7, 8]}], [{'ids': [99]}, {'ids': [3]}], [{'ids': [1000]}]]
    rangos = A.rango_gold(grupos, [5, 3, 8, 1])
    assert rangos == [3, 2, None]
    assert A.recall_at(rangos, 2) == pytest.approx(1 / 3)


def test_kappa():
    assert A.kappa([('a', 'a'), ('b', 'b')]) == 1.0
    assert A.kappa([('a', 'b'), ('b', 'a')]) == -1.0
    assert A.kappa([]) is None


def test_desempate_y_final():
    e = lambda v, d: {'rol': 'estudiante', 'veredicto': v, 'dano': d}
    assert not A.necesita_experto([e('correcta', 'ninguno')])
    assert A.necesita_experto([e('correcta', 'peligroso')])
    assert A.necesita_experto([e('correcta', 'ninguno'), e('incorrecta', 'ninguno')])
    assert A.necesita_experto([e('correcta', 'ninguno'), e('correcta', 'enganoso')])
    assert not A.necesita_experto([e('parcial', 'ninguno'), e('parcial', 'leve')])
    assert A.final([e('parcial', 'ninguno'), e('parcial', 'leve')])['dano'] == 'leve'
    assert A.final([e('correcta', 'ninguno'), e('incorrecta', 'ninguno')]) is None
    exp = {'rol': 'experto', 'veredicto': 'incorrecta', 'dano': 'enganoso'}
    assert A.final([e('correcta', 'ninguno'), e('incorrecta', 'ninguno'), exp]) is exp


def test_grupo_por_perfil():
    assert A.grupo_de({'grupo': 'general', 'perfil': {'area': 'derecho'}}) == 'derecho'
    assert A.grupo_de({'grupo': 'general', 'perfil': {'area': 'sociales', 'formacion_juridica': 'trabajo'}}) == 'derecho'
    assert A.grupo_de({'grupo': 'general', 'perfil': {'area': 'fisico_mat', 'formacion_juridica': 'materias'}}) == 'no_derecho'
    assert A.grupo_de({'grupo': 'lego', 'perfil': {'area': 'derecho'}}) == 'lego'


def test_lugares_mencionados():
    assert A.lugares_mencionados('mi jefe me manda mensajes, es delito?') == []
    assert A.lugares_mencionados('trabajo en qro y me acosan') == ['Querétaro']
    assert A.lugares_mencionados('me pasó en el df') == ['CDMX']
    assert A.lugares_mencionados('en la Ciudad de Mexico') == ['CDMX']
    assert A.lugares_mencionados('qué dice el cnpp') == []          # ley procesal: no fija el estado


def test_sus():
    assert A.sus([5, 1] * 5) == 100.0
    assert A.sus([1, 5] * 5) == 0.0
    assert A.sus([3] * 9) is None


# ── store + API contra un Postgres desechable ────────────────────────────────
CFGS: list = []   # configuraciones con las que se llamó al asistente falso
DSN = os.environ.get('ESTUDIO_TEST_DSN')
db = pytest.mark.skipif(not DSN, reason='ESTUDIO_TEST_DSN no definido (Postgres desechable)')


@pytest.fixture
def cliente(tmp_path):
    import psycopg
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from study.api import make_router
    from study.store import StudyStore

    connect = lambda: psycopg.connect(DSN)  # noqa: E731
    with connect() as c:
        c.execute('DROP TABLE IF EXISTS estudio_prompts, estudio_kioscos, estudio_calificaciones, estudio_turnos, estudio_intentos, '
                  'estudio_participantes, estudio_codigos, estudio_estudios CASCADE')
    (tmp_path / 'prueba.yaml').write_text(SPEC_YAML)
    store = StudyStore(connect, tmp_path)
    llamadas = []

    def chat_stream(messages, cfg):
        CFGS.append(cfg)
        llamadas.append(messages)
        yield {'stage': 'retrieving'}
        yield {'stage': 'hyde', 'passage': 'borrador'}
        yield {'stage': 'context', 'chunks': [{'id': 7, 'rank': 1, 'source': 's', 'text': 'Art. 179'}], 'ranking': [7, 8]}
        for p in ('Sí, ', 'es ', 'delito.'):
            yield {'stage': 'token', 'text': p}
        yield {'stage': 'done', 'seconds': 0.1}

    gold_refs = lambda t: [[{'source': 's', 'article': '179', 'label': 'CDMX 179'}]] if '179' in t else []  # noqa: E731
    resolver = lambda grupos: [[dict(x, ids=[7]) for x in g] for g in grupos]  # noqa: E731
    app = FastAPI()
    app.include_router(make_router(store=store, chat_stream=chat_stream, gold_refs=gold_refs, resolver_gold=resolver,
                                   sistema_de=lambda cfg: cfg.get('sistema') or 'PROMPT DEL TEMA',
                                   static_dir=tmp_path, current_email=lambda r: 'admin@x', es_admin=lambda e: True))
    return TestClient(app), store, llamadas


def _eventos(r):
    """Los eventos SSE de una respuesta en streaming."""
    return [_json.loads(l[6:]) for l in r.text.split('\n\n') if l.startswith('data: ')]


def _texto(r):
    return ''.join(e['text'] for e in _eventos(r) if e['stage'] == 'token')


@db
def test_flujo_completo(cliente):
    c, store, llamadas = cliente
    assert c.post('/api/estudio/p/estado', headers={'X-Codigo': 'NADA-NADA'}).status_code == 403
    [p1] = c.post('/api/estudios/prueba/codigos', json={'tipo': 'participante', 'grupo': 'lego', 'n': 1}).json()['codigos']
    [e1, e2] = c.post('/api/estudios/prueba/codigos', json={'tipo': 'calificador', 'grupo': 'estudiante', 'n': 2}).json()['codigos']
    [k1] = c.post('/api/estudios/prueba/codigos', json={'tipo': 'calificador', 'grupo': 'experto', 'n': 1}).json()['codigos']
    H = {'X-Codigo': p1.lower().replace('-', '')}           # el código se normaliza
    assert c.post('/api/estudio/p/estado', headers=H).json()['error'] == 'El estudio no está abierto en este momento.'
    c.post('/api/estudios/prueba/estado', json={'estado': 'abierto'})
    assert store.obtener('prueba')['updated_by'] == 'repo'      # abrir no cuenta como editar

    assert c.post('/api/estudio/p/consentir', headers=H, json={}).status_code == 400
    assert 'Carrera' in c.post('/api/estudio/p/consentir', headers=H, json={'acepto': True, 'perfil': {'formacion': 'ninguna'}}).json()['error']
    est = c.post('/api/estudio/p/consentir', headers=H, json={'acepto': True, 'perfil': {'formacion': 'ninguna', 'carrera': ' Física ', 'nombre': 'X'}}).json()
    assert len(est['escenarios']) == 2 and 'referencia' not in repr(est)
    # Práctica: responde el asistente pero no se guarda; máximo 2; después de «listo» ya no.
    assert est['tutorial_hecho'] is False and est['tutorial']['ejemplo']
    n0 = len(llamadas)
    assert 'Sí, es delito.' == _texto(c.post('/api/estudio/p/practica_stream', headers=H, json={'mensaje': 'prueba'}))
    c.post('/api/estudio/p/practica_stream', headers=H, json={'mensaje': 'otra'})
    assert c.post('/api/estudio/p/practica_stream', headers=H, json={'mensaje': 'tercera'}).status_code == 400
    assert len(llamadas) == n0 + 2 and store.participante(p1)['practicas'] == 2
    assert c.post('/api/estudio/p/tutorial_listo', headers=H).json()['tutorial_hecho'] is True
    llamadas.clear()
    assert store.participante(p1)['perfil'] == {'formacion': 'ninguna', 'carrera': 'Física'}   # campos desconocidos se descartan
    s1 = est['escenarios'][0]['id']
    it = c.post('/api/estudio/p/iniciar', headers=H, json={'escenario': s1}).json()['intento']
    assert c.post('/api/estudio/p/iniciar', headers=H, json={'escenario': 'zzz'}).status_code == 403
    evs = _eventos(c.post('/api/estudio/p/preguntar_stream', headers=H, json={'intento': it['id'], 'mensaje': 'hola'}))
    assert evs[-1]['stage'] == 'done' and evs[-1]['fuentes'][0]['texto'] == 'Art. 179'
    c.post('/api/estudio/p/preguntar_stream', headers=H, json={'intento': it['id'], 'mensaje': 'y luego'})
    assert len(llamadas[-1]) == 3                                        # historial: u, a, u
    t1 = store.export('prueba')['turnos'][0]
    assert t1['config']['tema'] == 't' and t1['ranking'] == [7, 8]  # config y ranking por turno, para reanalizar
    assert c.post('/api/estudio/p/preguntar_stream', headers=H, json={'intento': it['id'], 'mensaje': 'otra'}).status_code == 400  # max_turnos 2
    # Pasar a las preguntas: ya no se puede preguntar (ve la conversación solo para leer).
    c.post('/api/estudio/p/a_preguntas', headers=H, json={'intento': it['id']})
    assert c.post('/api/estudio/p/preguntar_stream', headers=H, json={'intento': it['id'], 'mensaje': 'x'}).status_code == 403
    assert c.post('/api/estudio/p/iniciar', headers=H, json={'escenario': s1}).json()['intento']['preguntas_at']
    assert c.post('/api/estudio/p/terminar', headers=H, json={'intento': it['id'], 'respuestas': {'p1': 'si'}}).status_code == 400
    c.post('/api/estudio/p/terminar', headers=H, json={'intento': it['id'], 'respuestas': {'p1': 'si'}, 'confianza': 5, 'actuaria': 'si', 'detecto': 'no',
                                                     'comentario': 'todo claro'})
    assert c.post('/api/estudio/p/preguntar_stream', headers=H, json={'intento': it['id'], 'mensaje': 'x'}).status_code == 403

    # Calificación: cada turno lo califican 2 estudiantes; un desacuerdo va a la experta.
    G = lambda k: {'X-Codigo': k}  # noqa: E731
    t = c.post('/api/estudio/c/siguiente', headers=G(e1)).json()
    assert t['turno'] and t['escenario']['referencia'] and 'grupo' not in repr(t['turno'])
    cal = {'veredicto': 'correcta', 'dano': 'ninguno', 'error_jurisdiccion': 'no', 'cita': 'respalda'}
    t2 = c.post('/api/estudio/c/calificar', headers=G(e1), json={'turno': t['turno']['id'], **cal}).json()
    assert t2['turno']['id'] != t['turno']['id']                         # no vuelve a darle el mismo
    c.post('/api/estudio/c/calificar', headers=G(e1), json={'turno': t2['turno']['id'], **cal})
    assert c.post('/api/estudio/c/siguiente', headers=G(e1)).json()['turno'] is None
    u = c.post('/api/estudio/c/siguiente', headers=G(e2)).json()
    c.post('/api/estudio/c/calificar', headers=G(e2), json={'turno': u['turno']['id'], **cal, 'veredicto': 'incorrecta'})
    assert c.post('/api/estudio/c/siguiente', headers=G(k1)).json()['turno']['id'] == u['turno']['id']
    assert c.post('/api/estudio/c/calificar', headers=G(k1), json={'turno': u['turno']['id'], 'veredicto': 'x'}).status_code == 400
    assert c.post('/api/estudio/c/siguiente', headers=G(p1)).status_code == 403   # un código de participante no califica

    assert [i['comentario'] for i in store.export('prueba')['intentos'] if i['fin']] == ['todo claro']
    d = c.get(f'/api/estudios/prueba/participantes/{p1}').json()
    it_d = next(i for i in d['intentos'] if i['fin'])
    assert it_d['preguntas'][0]['correcta'] and it_d['turnos'][0]['respuesta'] and it_d['comentario'] == 'todo claro'
    assert c.get('/api/estudios/prueba/participantes/NADA-NADA').status_code == 404
    res = c.get('/api/estudios/prueba/resumen').json()
    assert res['lego']['comprension'] is not None and res['_acuerdo']['pares'] == 1
    exp = c.get('/api/estudios/prueba/export').json()
    if s1 == 'a':
        assert exp['turnos'][0]['rangos'] == [1]

    # Variantes: dos participantes del mismo grupo reciben variantes distintas de «c».
    qs = c.post('/api/estudios/prueba/codigos', json={'tipo': 'participante', 'grupo': 'estudiante', 'n': 4}).json()['codigos']
    perfil = {'formacion': 'estudiante', 'carrera': 'Derecho'}
    for q in qs:
        c.post('/api/estudio/p/consentir', headers={'X-Codigo': q}, json={'acepto': True, 'perfil': perfil})
    vs = [store.participante(q)['variantes']['c'] for q in qs if 'c' in store.participante(q)['asignados']]
    assert len(vs) >= 2 and sorted(vs[:2]) == ['v1', 'v2']   # los dos primeros a quienes les toca «c»: una de cada

    # Kiosco: solo con token válido y estudio abierto; cada «nuevo» es un código distinto, grupo general.
    assert c.post('/api/estudio/k/nuevo', headers={'X-Kiosco': 'falso'}).status_code == 403
    tok = c.post('/api/estudios/prueba/kioscos', json={'nota': 'sala 1'}).json()['token']
    k1 = c.post('/api/estudio/k/nuevo', headers={'X-Kiosco': tok}).json()['codigo']
    k2 = c.post('/api/estudio/k/nuevo', headers={'X-Kiosco': tok}).json()['codigo']
    assert k1 != k2 and c.post('/api/estudio/p/estado', headers={'X-Codigo': k1}).json()['consentido'] is False
    assert c.get('/api/estudios/prueba/kioscos').json()[0]['participantes'] == 2
    assert c.get('/api/estudios/prueba/kioscos').json()[0]['token'] is None      # del kiosco solo se guarda el hash
    # Enlace público: con cupo; el token sí se guarda (es el enlace que se comparte).
    assert c.post('/api/estudios/prueba/kioscos', json={'tipo': 'enlace'}).status_code == 400    # sin cupo
    link = c.post('/api/estudios/prueba/kioscos', json={'tipo': 'enlace', 'cupo': 1, 'nota': 'whatsapp'}).json()['token']
    st = c.post('/api/estudio/k/estado', headers={'X-Kiosco': link}).json()
    assert st['tipo'] == 'enlace' and st['lleno'] is False
    e1 = c.post('/api/estudio/k/nuevo', headers={'X-Kiosco': link}).json()['codigo']
    lleno = c.post('/api/estudio/k/nuevo', headers={'X-Kiosco': link})
    assert lleno.status_code == 403 and 'completó' in lleno.json()['error']
    assert c.post('/api/estudio/k/estado', headers={'X-Kiosco': link}).json()['lleno'] is True
    en = [k for k in c.get('/api/estudios/prueba/kioscos').json() if k['tipo'] == 'enlace'][0]
    assert en['token'] == link and en['participantes'] == 1 and en['cupo'] == 1
    c.post('/api/estudio/p/consentir', headers={'X-Codigo': e1}, json={'acepto': True, 'perfil': {'formacion': 'ninguna', 'carrera': 'X'}})
    assert [p['origen'] for p in store.export('prueba')['participantes'] if p['codigo'] == e1] == [f"enlace #{en['id']}"]
    kid = c.get('/api/estudios/prueba/kioscos').json()[0]['id']
    c.post(f'/api/estudios/prueba/kioscos/{kid}/activo', json={'activo': False})
    assert c.post('/api/estudio/k/nuevo', headers={'X-Kiosco': tok}).status_code == 403

    # Retirarse borra todo y el código deja de servir.
    c.post('/api/estudio/p/retirar', headers=H)
    assert c.get('/api/estudios/prueba/export').json()['turnos'] == []
    assert c.post('/api/estudio/p/estado', headers=H).status_code == 403


@db
def test_streaming_guarda_el_turno_completo(cliente):
    c, store, llamadas = cliente
    c.post('/api/estudios/prueba/estado', json={'estado': 'abierto'})
    [p] = c.post('/api/estudios/prueba/codigos', json={'tipo': 'participante', 'grupo': 'general', 'n': 1}).json()['codigos']
    H = {'X-Codigo': p}
    est = c.post('/api/estudio/p/consentir', headers=H, json={'acepto': True, 'perfil': {'formacion': 'ninguna', 'carrera': 'X'}}).json()
    it = c.post('/api/estudio/p/iniciar', headers=H, json={'escenario': est['escenarios'][0]['id']}).json()['intento']
    assert c.post('/api/estudio/p/a_preguntas', headers=H, json={'intento': it['id']}).status_code == 403   # sin preguntas aún
    r = c.post('/api/estudio/p/preguntar_stream', headers=H, json={'intento': it['id'], 'mensaje': '¿es delito?'})
    evs = [_json.loads(l[6:]) for l in r.text.split('\n\n') if l.startswith('data: ')]
    assert ''.join(e['text'] for e in evs if e['stage'] == 'token') == 'Sí, es delito.'
    assert evs[-1]['stage'] == 'done' and evs[-1]['fuentes'][0]['texto'] == 'Art. 179'
    [t] = store.export('prueba')['turnos']
    assert t['respuesta'] == 'Sí, es delito.' and t['ranking'] == [7, 8] and t['busqueda_debug']['hyde_passage'] == 'borrador'
    # La práctica en streaming no se guarda como turno; la conversación previa de la práctica la manda la página.
    c.post('/api/estudio/p/practica_stream', headers=H, json={'mensaje': 'hola', 'historial': [{'pregunta': '¿qué es?', 'respuesta': 'Es…'}]})
    assert [m['role'] for m in llamadas[-1]] == ['user', 'assistant', 'user'] and llamadas[-1][-1]['content'] == 'hola'
    assert len(store.export('prueba')['turnos']) == 1 and store.participante(p)['practicas'] == 1


@db
def test_condiciones_fases_y_ultima_situacion(cliente):
    c, store, llamadas = cliente
    c.post('/api/estudios/prueba/estado', json={'estado': 'abierto'})
    cods = c.post('/api/estudios/prueba/codigos', json={'tipo': 'participante', 'grupo': 'general', 'n': 2}).json()['codigos']
    perfil = {'formacion': 'ninguna', 'carrera': 'X'}
    vistas = {}
    for cod in cods:
        est = c.post('/api/estudio/p/consentir', headers={'X-Codigo': cod}, json={'acepto': True, 'perfil': perfil}).json()
        assert 'condicion' not in repr(est) and 'sencillo' not in repr(est)      # la persona no sabe qué le tocó
        vistas[cod] = est
    conds = {cod: store.participante(cod)['condicion'] for cod in cods}
    assert sorted(conds.values()) == ['actual', 'sencillo'] and store.participante(cods[0])['fase'] == 'principal'
    # Cada quien conversa con el prompt de su condición; el turno guarda cuál fue (texto aparte, por md5).
    for cod in cods:
        H = {'X-Codigo': cod}
        e1, e2 = vistas[cod]['escenarios']
        it = c.post('/api/estudio/p/iniciar', headers=H, json={'escenario': e1['id']}).json()['intento']
        CFGS.clear()
        c.post('/api/estudio/p/preguntar_stream', headers=H, json={'intento': it['id'], 'mensaje': '¿es delito?'})
        assert CFGS[-1].get('sistema') == ('Habla sencillo' if conds[cod] == 'sencillo' else None)
        ok = {'confianza': 4, 'actuaria': 'si', 'detecto': 'no'}
        resp = {q['id']: 'otra' if 'otra' in q['opciones'] else 'si' for q in e1['preguntas']}
        resp.update({q['id'] + '__texto': 'art. 181 Quintus' for q in e1['preguntas'] if 'otra' in q['opciones']})
        assert c.post('/api/estudio/p/terminar', headers=H, json={'intento': it['id'], 'respuestas': resp, **ok}).status_code == 200
        # La segunda (y última) situación exige además la pregunta de `ultima_situacion`.
        it2 = c.post('/api/estudio/p/iniciar', headers=H, json={'escenario': e2['id']}).json()['intento']
        c.post('/api/estudio/p/preguntar_stream', headers=H, json={'intento': it2['id'], 'mensaje': 'otra duda'})
        r2 = {q['id']: 'si' for q in e2['preguntas']}
        assert c.post('/api/estudio/p/terminar', headers=H, json={'intento': it2['id'], 'respuestas': r2, **ok}).status_code == 400
        assert c.post('/api/estudio/p/terminar', headers=H, json={'intento': it2['id'], 'respuestas': {**r2, '_estado': 'cdmx', 'basura': 1}, **ok}).status_code == 200
    exp = c.get('/api/estudios/prueba/export').json()
    prompts = {exp['prompts'][t['sistema_md5']] for t in exp['turnos']}
    assert prompts == {'Habla sencillo', 'PROMPT DEL TEMA'}
    assert all('sistema' not in t['config'] and t['config']['condicion'] in ('actual', 'sencillo') for t in exp['turnos'])
    ult = [i['respuestas'] for i in exp['intentos'] if '_estado' in (i['respuestas'] or {})]
    assert len(ult) == 2 and all('basura' not in r for r in ult)
    assert exp['turnos'][0]['analisis']['palabras'] == 3 and exp['intentos'][0]['version'] >= 1
    res = c.get('/api/estudios/prueba/resumen?fase=principal').json()
    assert set(res['_por_condicion']) == {'actual', 'sencillo'} and res['_por_condicion']['sencillo']['situaciones'] == 2
    assert c.get('/api/estudios/prueba/resumen?fase=piloto').json()['_por_condicion'] == {}
    # Marcar «piloto» solo toca a quienes no tienen fase.
    assert c.post('/api/estudios/prueba/fase', json={'fase': 'piloto'}).json()['marcados'] == 0


def test_limpiar_respuestas():
    from study.validar import cargar, limpiar_respuestas
    spec = cargar(SPEC_YAML)[0]
    b = spec['escenarios'][1]
    r = {'p1': 'otra', 'p1__texto': ' art. 181 Quintus ', 'x': 1, '_estado': 'cdmx'}
    assert limpiar_respuestas(spec, b, r, False) == {'p1': 'otra', 'p1__texto': 'art. 181 Quintus'}
    assert limpiar_respuestas(spec, b, r, True) == {'p1': 'otra', 'p1__texto': 'art. 181 Quintus', '_estado': 'cdmx'}
    assert limpiar_respuestas(spec, b, {'p1': 'si', 'p1__texto': 'no cuenta', '_estado': 'zzz'}, True) == {'p1': 'si'}
    assert A.puntuar_comprension(b, {'p1': 'otra', 'p1__texto': 'x'})['aciertos'] == 0     # «otra» cuenta como incorrecta


def test_analizar_respuesta():
    g = [[{'source': 'Código Penal del Estado de Querétaro.md', 'article': '167 Ter'}]]
    a = A.analizar_respuesta('Según el Código Penal para el Estado de Morelos, artículo 158… y el art. 167 TER del Código Penal del Estado de Querétaro.', g)
    assert a['cita_ley_gold'] and a['cita_articulo_gold'] and a['otros_estados'] == ['Morelos'] and a['primera_ley_es_otra']
    assert A.analizar_respuesta('Para orientarte necesito saber en qué estado ocurrió.', g)['pide_lugar']
    g2 = [[{'source': 'Código Penal de la Ciudad de México.md', 'article': '179'}]]
    assert not A.analizar_respuesta('El artículo 179 Bis del Código Penal de la Ciudad de México', g2)['cita_articulo_gold']
    assert A.analizar_respuesta('art. 179 del Código Penal del Distrito Federal', g2)['cita_articulo_gold']


def test_metricas_corregidas():
    # «citatorio»: los hechos fueron en Querétaro; Ariel vive en la Ciudad de México.
    g = [[{'source': 'Código Penal del Estado de Querétaro.md', 'article': '1'}]]
    bien = 'La competencia recae en las autoridades de Querétaro y no en las de la Ciudad de México, donde vives.'
    a = A.analizar_respuesta(bien, g)
    assert a['otros_estados'] == ['CDMX']            # la métrica original lo cuenta como error
    assert a['otro_codigo_estatal'] == []            # la corregida no: solo menciona el lugar
    mal = 'Conforme al artículo 141 del Código Penal para el Distrito Federal, las lesiones se sancionan…'
    assert A.analizar_respuesta(mal, g)['otro_codigo_estatal'] == ['CDMX']
    assert A.analizar_respuesta('Según el Código Penal Federal, artículo 288…', g)['otro_codigo_estatal'] == []   # el CPF no es otro estado
    assert A.analizar_respuesta('El Código Penal del Estado de Querétaro, artículo 1, …', g)['otro_codigo_estatal'] == []
    # Pedir el estado: explicar «la ley del lugar donde ocurrieron» no es pedirlo.
    explica = 'Los delitos se juzgan conforme a las leyes del lugar donde ocurrieron los hechos.'
    assert A.analizar_respuesta(explica, g)['pide_lugar'] and not A.analizar_respuesta(explica, g)['pide_lugar_estricto']
    assert A.analizar_respuesta('¿En qué estado ocurrieron los hechos?', g)['pide_lugar_estricto']
    assert A.analizar_respuesta('Es necesario precisar en qué estado de la República ocurrieron los hechos.', g)['pide_lugar_estricto']
    assert A.analizar_respuesta('Indícame en qué entidad pasó, por favor.', g)['pide_lugar_estricto']


def test_auth_deja_pasar_solo_rutas_del_estudio():
    import auth
    assert '/estudio' in auth.PUBLIC_STUDY and '/estudios' not in auth.PUBLIC_STUDY
    assert '/api/estudios/x'.startswith(auth.PUBLIC_PREFIXES) is False
    assert '/api/estudio/k/nuevo'.startswith(auth.PUBLIC_PREFIXES)


def test_escalas_situacion():
    """Escalas 1–5 al terminar cada situación (26-oct): se validan, se muestran y solo se guardan enteros del 1 al 5."""
    from study.validar import cargar, limpiar_respuestas
    import yaml
    spec = cargar(SPEC_YAML)[0]
    spec['escalas_situacion'] = [{'id': 'confianza_asistente', 'texto': '¿Qué tanta confianza…?', 'minimo': 'nada', 'maximo': 'mucha'}]
    assert validar(yaml.safe_dump(spec, allow_unicode=True)) == []
    assert vista_publica(spec, [])['escalas_situacion'] == spec['escalas_situacion']
    b = spec['escenarios'][1]
    r = {'p1': 'si', 'escala_confianza_asistente': 4, 'escala_otra': 3}
    assert limpiar_respuestas(spec, b, r, False) == {'p1': 'si', 'escala_confianza_asistente': 4}
    for malo in (0, 6, '4', True, None):
        assert 'escala_confianza_asistente' not in limpiar_respuestas(spec, b, {'escala_confianza_asistente': malo}, False)
    spec['escalas_situacion'] = [{'id': 'A B', 'texto': 'x'}, {'id': 'ok', 'texto': ''}]
    assert sum('escalas_situacion' in e for e in validar(yaml.safe_dump(spec, allow_unicode=True))) == 2


def test_consulado_es_valido():
    from bench import gold_refs
    consulado = SEED.parent / 'ronda2_consulado.yaml'
    assert validar(consulado.read_text(), lambda t: gold_refs('', [{'kind': 'must', 'text': t}])) == []
