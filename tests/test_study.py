"""Estudio con usuarios (apps/rewrite_lab/study/).

Las pruebas de cálculos y validación no necesitan nada. Las del store y la API necesitan un
Postgres DESECHABLE: `ESTUDIO_TEST_DSN=postgresql://test@127.0.0.1:55432/estudio_test`. Borran las
tablas estudio_* al empezar, así que nunca apuntes esa variable a la BD de prod.
"""
from __future__ import annotations

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
    preguntas: [{id: p1, texto: '¿Pregunta?', opciones: {si: Sí, no: 'No'}, correcta: 'no'}]
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


def test_sus():
    assert A.sus([5, 1] * 5) == 100.0
    assert A.sus([1, 5] * 5) == 0.0
    assert A.sus([3] * 9) is None


# ── store + API contra un Postgres desechable ────────────────────────────────
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
        c.execute('DROP TABLE IF EXISTS estudio_kioscos, estudio_calificaciones, estudio_turnos, estudio_intentos, '
                  'estudio_participantes, estudio_codigos, estudio_estudios CASCADE')
    (tmp_path / 'prueba.yaml').write_text(SPEC_YAML)
    store = StudyStore(connect, tmp_path)
    llamadas = []

    def chat(messages, cfg):
        llamadas.append(messages)
        return {'answer': f'respuesta {len(messages)}', 'chunks': [{'id': 7, 'rank': 1, 'source': 's', 'text': 'Art. 179'}],
                'ranking': [7, 8, 9], 'seconds': 0.1}

    gold_refs = lambda t: [[{'source': 's', 'article': '179', 'label': 'CDMX 179'}]] if '179' in t else []  # noqa: E731
    resolver = lambda grupos: [[dict(x, ids=[7]) for x in g] for g in grupos]  # noqa: E731
    app = FastAPI()
    app.include_router(make_router(store=store, chat=chat, gold_refs=gold_refs, resolver_gold=resolver,
                                   static_dir=tmp_path, current_email=lambda r: 'admin@x', es_admin=lambda e: True))
    return TestClient(app), store, llamadas


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
    assert c.post('/api/estudio/p/practica', headers=H, json={'mensaje': 'prueba'}).json()['respuesta']
    c.post('/api/estudio/p/practica', headers=H, json={'mensaje': 'otra'})
    assert c.post('/api/estudio/p/practica', headers=H, json={'mensaje': 'tercera'}).status_code == 400
    assert len(llamadas) == n0 + 2 and store.participante(p1)['practicas'] == 2
    assert c.post('/api/estudio/p/tutorial_listo', headers=H).json()['tutorial_hecho'] is True
    llamadas.clear()
    assert store.participante(p1)['perfil'] == {'formacion': 'ninguna', 'carrera': 'Física'}   # campos desconocidos se descartan
    s1 = est['escenarios'][0]['id']
    it = c.post('/api/estudio/p/iniciar', headers=H, json={'escenario': s1}).json()['intento']
    assert c.post('/api/estudio/p/iniciar', headers=H, json={'escenario': 'zzz'}).status_code == 403
    r = c.post('/api/estudio/p/preguntar', headers=H, json={'intento': it['id'], 'mensaje': 'hola'}).json()
    assert r['respuesta'] == 'respuesta 1' and r['fuentes'][0]['texto'] == 'Art. 179'
    c.post('/api/estudio/p/preguntar', headers=H, json={'intento': it['id'], 'mensaje': 'y luego'})
    assert len(llamadas[-1]) == 3                                        # historial: u, a, u
    assert c.post('/api/estudio/p/preguntar', headers=H, json={'intento': it['id'], 'mensaje': 'otra'}).status_code == 400  # max_turnos 2
    assert c.post('/api/estudio/p/terminar', headers=H, json={'intento': it['id'], 'respuestas': {'p1': 'si'}}).status_code == 400
    c.post('/api/estudio/p/terminar', headers=H, json={'intento': it['id'], 'respuestas': {'p1': 'si'}, 'confianza': 5, 'actuaria': 'si', 'detecto': 'no'})
    assert c.post('/api/estudio/p/preguntar', headers=H, json={'intento': it['id'], 'mensaje': 'x'}).status_code == 403

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
    assert 'token' not in repr(c.get('/api/estudios/prueba/kioscos').json())
    kid = c.get('/api/estudios/prueba/kioscos').json()[0]['id']
    c.post(f'/api/estudios/prueba/kioscos/{kid}/activo', json={'activo': False})
    assert c.post('/api/estudio/k/nuevo', headers={'X-Kiosco': tok}).status_code == 403

    # Retirarse borra todo y el código deja de servir.
    c.post('/api/estudio/p/retirar', headers=H)
    assert c.get('/api/estudios/prueba/export').json()['turnos'] == []
    assert c.post('/api/estudio/p/estado', headers=H).status_code == 403


def test_auth_deja_pasar_solo_rutas_del_estudio():
    import auth
    assert '/estudio' in auth.PUBLIC_STUDY and '/estudios' not in auth.PUBLIC_STUDY
    assert '/api/estudios/x'.startswith(auth.PUBLIC_PREFIXES) is False
    assert '/api/estudio/k/nuevo'.startswith(auth.PUBLIC_PREFIXES)
