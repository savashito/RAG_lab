"""Dónde vive el estudio con usuarios (tablas `estudio_*` en la BD del app).

  · estudio_estudios: la definición (estudio.yaml) editable en /estudios, con estado
    borrador → abierto → cerrado. Se siembra desde study/estudios/*.yaml igual que los formularios:
    el repo solo actualiza estudios en borrador que nadie ha editado desde la app.
  · estudio_codigos: códigos de acceso seudónimos (XXXX-XXXX). Un código de participante entra a
    /estudio; uno de calificador, a /calificar. No se guardan nombres ni correos de participantes.
  · estudio_participantes / estudio_intentos / estudio_turnos: lo que hizo cada código. Los
    escenarios son ficticios y la persona consintió que se registre lo que escribe.
  · estudio_calificaciones: calificación a ciegas de cada respuesta del asistente.

Retirarse del estudio borra en cascada todo lo del código (participante, intentos, turnos y sus
calificaciones).
"""
from __future__ import annotations

import hashlib
import json
import random
import secrets
from pathlib import Path

from study.analisis import asignar, asignar_variante, necesita_experto, puntuar_comprension
from study.validar import cargar, escenario_efectivo, validar

SCHEMA = """
CREATE TABLE IF NOT EXISTS estudio_estudios (
    id text PRIMARY KEY, titulo text NOT NULL,
    estado text NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador', 'abierto', 'cerrado')),
    version int NOT NULL DEFAULT 1, spec_yaml text NOT NULL,
    updated_by text, updated_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS estudio_codigos (
    codigo text PRIMARY KEY, estudio text NOT NULL REFERENCES estudio_estudios(id),
    tipo text NOT NULL CHECK (tipo IN ('participante', 'calificador')),
    grupo text NOT NULL, nota text, activo boolean NOT NULL DEFAULT true,
    creado_por text, creado_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS estudio_participantes (
    codigo text PRIMARY KEY REFERENCES estudio_codigos(codigo) ON DELETE CASCADE,
    perfil jsonb NOT NULL DEFAULT '{}', asignados jsonb NOT NULL DEFAULT '[]', cierre jsonb,
    consentimiento_at timestamptz DEFAULT now(), terminado_at timestamptz);
CREATE TABLE IF NOT EXISTS estudio_intentos (
    id serial PRIMARY KEY,
    codigo text NOT NULL REFERENCES estudio_participantes(codigo) ON DELETE CASCADE,
    escenario text NOT NULL, inicio timestamptz DEFAULT now(), fin timestamptz,
    respuestas jsonb, comprension jsonb, confianza int, actuaria text,
    UNIQUE (codigo, escenario));
CREATE TABLE IF NOT EXISTS estudio_turnos (
    id serial PRIMARY KEY,
    intento_id int NOT NULL REFERENCES estudio_intentos(id) ON DELETE CASCADE,
    n int NOT NULL, ts timestamptz DEFAULT now(), pregunta text NOT NULL, busqueda text,
    respuesta text, contexto jsonb, ranking jsonb, segundos real, error text);
CREATE TABLE IF NOT EXISTS estudio_calificaciones (
    id serial PRIMARY KEY,
    turno_id int NOT NULL REFERENCES estudio_turnos(id) ON DELETE CASCADE,
    calificador text NOT NULL REFERENCES estudio_codigos(codigo), rol text NOT NULL,
    veredicto text NOT NULL, dano text NOT NULL, error_jurisdiccion text, cita text, notas text,
    ts timestamptz DEFAULT now(), UNIQUE (turno_id, calificador));
-- Variante sorteada de cada escenario ({escenario: variante}) y pregunta de detección.
ALTER TABLE estudio_participantes ADD COLUMN IF NOT EXISTS variantes jsonb NOT NULL DEFAULT '{}';
ALTER TABLE estudio_intentos ADD COLUMN IF NOT EXISTS variante text;
ALTER TABLE estudio_intentos ADD COLUMN IF NOT EXISTS detecto text;
ALTER TABLE estudio_intentos ADD COLUMN IF NOT EXISTS detecto_cual text;
-- Práctica antes de las situaciones: cuándo la terminó y cuántas preguntas de práctica hizo (no se guardan).
ALTER TABLE estudio_participantes ADD COLUMN IF NOT EXISTS tutorial_at timestamptz;
-- Por turno: configuración exacta del asistente y lo que hizo la búsqueda (borrador HyDE, sub-preguntas,
-- routing), para poder reanalizar las preguntas de participantes en experimentos futuros.
ALTER TABLE estudio_turnos ADD COLUMN IF NOT EXISTS config jsonb;
-- Cuándo pasó a las preguntas de comprensión: desde ahí ya no puede preguntarle al asistente
-- (ve la conversación solo para leer), para que las opciones no contaminen sus preguntas.
ALTER TABLE estudio_intentos ADD COLUMN IF NOT EXISTS preguntas_at timestamptz;
ALTER TABLE estudio_intentos ADD COLUMN IF NOT EXISTS comentario text;
ALTER TABLE estudio_turnos ADD COLUMN IF NOT EXISTS busqueda_debug jsonb;
ALTER TABLE estudio_participantes ADD COLUMN IF NOT EXISTS practicas int NOT NULL DEFAULT 0;
-- Modo kiosco: una computadora autorizada por un admin crea un código nuevo por cada participante.
-- Solo se guarda el hash del token; el token vive en el navegador de esa computadora.
CREATE TABLE IF NOT EXISTS estudio_kioscos (
    id serial PRIMARY KEY, estudio text NOT NULL REFERENCES estudio_estudios(id),
    token_hash text NOT NULL UNIQUE, grupo text NOT NULL, nota text, activo boolean NOT NULL DEFAULT true,
    participantes int NOT NULL DEFAULT 0, creado_por text, creado_at timestamptz DEFAULT now());
"""

_ALFABETO = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'   # sin 0/O, 1/I/L


def nuevo_codigo() -> str:
    s = ''.join(secrets.choice(_ALFABETO) for _ in range(8))
    return f'{s[:4]}-{s[4:]}'


def normalizar_codigo(c: str) -> str:
    c = ''.join(ch for ch in (c or '').upper() if ch in _ALFABETO)
    return f'{c[:4]}-{c[4:]}' if len(c) == 8 else ''


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class NoPermitido(Exception):
    """Código inválido, inactivo, de otro tipo o estudio no abierto."""


class StudyStore:
    def __init__(self, connect, seed_dir: Path, gold_refs=None):
        self.connect, self.seed_dir, self.gold_refs = connect, seed_dir, gold_refs
        with self.connect() as c, c.cursor() as cur:
            cur.execute(SCHEMA)
            c.commit()
        self.sembrar()

    def _q(self, sql, args=(), one=False, commit=False):
        with self.connect() as c, c.cursor() as cur:
            cur.execute(sql, args)
            rows = None
            if cur.description:
                cols = [d.name for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            if commit:
                c.commit()
        return (rows[0] if rows else None) if one else rows

    # ── definición del estudio ───────────────────────────────────────────────────
    def sembrar(self):
        if not self.seed_dir.is_dir():
            return
        for f in sorted(self.seed_dir.glob('*.yaml')):
            txt = f.read_text()
            if validar(txt):
                print(f'estudios: {f.name} no se sembró (tiene errores; corre tests/test_study.py)')
                continue
            spec, _ = cargar(txt)
            self._q("INSERT INTO estudio_estudios (id, titulo, estado, spec_yaml, updated_by) VALUES (%s,%s,%s,%s,'repo') "
                    "ON CONFLICT (id) DO UPDATE SET titulo = EXCLUDED.titulo, spec_yaml = EXCLUDED.spec_yaml, "
                    "version = estudio_estudios.version + 1, updated_at = now() "
                    "WHERE estudio_estudios.updated_by = 'repo' AND estudio_estudios.estado = 'borrador' "
                    "AND estudio_estudios.spec_yaml IS DISTINCT FROM EXCLUDED.spec_yaml",
                    (spec['id'], spec['titulo'], 'borrador', txt), commit=True)

    def lista(self) -> list[dict]:
        return self._q(
            "SELECT e.id, e.titulo, e.estado, e.version, e.updated_by, e.updated_at::text, "
            "(SELECT count(*) FROM estudio_participantes p JOIN estudio_codigos k USING (codigo) WHERE k.estudio = e.id) AS participantes, "
            "(SELECT count(*) FROM estudio_turnos t JOIN estudio_intentos i ON i.id = t.intento_id "
            " JOIN estudio_codigos k ON k.codigo = i.codigo WHERE k.estudio = e.id) AS turnos, "
            "(SELECT count(*) FROM estudio_calificaciones c JOIN estudio_codigos k ON k.codigo = c.calificador WHERE k.estudio = e.id) AS calificaciones "
            "FROM estudio_estudios e ORDER BY e.updated_at DESC")

    def obtener(self, eid: str) -> dict | None:
        return self._q("SELECT id, titulo, estado, version, spec_yaml, updated_by, updated_at::text "
                       "FROM estudio_estudios WHERE id = %s", (eid,), one=True)

    def spec(self, eid: str) -> dict:
        row = self.obtener(eid)
        return (cargar(row['spec_yaml'])[0] or {}) if row else {}

    def guardar(self, eid: str | None, spec_yaml: str, version: int, email: str) -> dict:
        errs = validar(spec_yaml, self.gold_refs)
        if errs:
            return {'errores': errs}
        spec, _ = cargar(spec_yaml)
        if eid and spec['id'] != eid:
            return {'errores': ['No se puede cambiar el «id» de un estudio existente.']}
        actual = self.obtener(spec['id'])
        if actual is None:
            self._q("INSERT INTO estudio_estudios (id, titulo, spec_yaml, updated_by) VALUES (%s,%s,%s,%s)",
                    (spec['id'], spec['titulo'], spec_yaml, email), commit=True)
        else:
            if actual['version'] != version:
                return {'errores': ['Alguien más guardó este estudio mientras lo editabas; recarga.'], 'conflicto': True}
            self._q("UPDATE estudio_estudios SET titulo=%s, spec_yaml=%s, version=version+1, updated_by=%s, "
                    "updated_at=now() WHERE id=%s", (spec['titulo'], spec_yaml, email, spec['id']), commit=True)
        return {'errores': [], **self.obtener(spec['id'])}

    def cambiar_estado(self, eid: str, estado: str, email: str) -> dict:
        # Abrir o cerrar no es editar: no cambia updated_by (así el repo puede seguir actualizando un
        # estudio en borrador que nadie ha editado desde la app).
        self._q("UPDATE estudio_estudios SET estado=%s, updated_at=now() WHERE id=%s", (estado, eid), commit=True)
        return self.obtener(eid)

    # ── códigos ──────────────────────────────────────────────────────────────────
    def crear_codigos(self, eid: str, tipo: str, grupo: str, n: int, nota: str, email: str) -> list[str]:
        out = []
        for _ in range(n):
            c = nuevo_codigo()
            self._q("INSERT INTO estudio_codigos (codigo, estudio, tipo, grupo, nota, creado_por) VALUES (%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT DO NOTHING", (c, eid, tipo, grupo, nota or None, email), commit=True)
            out.append(c)
        return out

    def codigos(self, eid: str) -> list[dict]:
        return self._q(
            "SELECT k.codigo, k.tipo, k.grupo, k.nota, k.activo, k.creado_at::text, "
            "p.consentimiento_at::text AS consentimiento_at, p.terminado_at::text AS terminado_at, "
            "(SELECT count(*) FROM estudio_intentos i WHERE i.codigo = k.codigo AND i.fin IS NOT NULL) AS escenarios_terminados, "
            "(SELECT count(*) FROM estudio_calificaciones c WHERE c.calificador = k.codigo) AS calificadas "
            "FROM estudio_codigos k LEFT JOIN estudio_participantes p USING (codigo) WHERE k.estudio = %s "
            "ORDER BY k.creado_at, k.codigo", (eid,))

    # ── kiosco ───────────────────────────────────────────────────────────────────
    def crear_kiosco(self, eid: str, grupo: str, nota: str, email: str) -> str:
        token = secrets.token_urlsafe(32)
        self._q("INSERT INTO estudio_kioscos (estudio, token_hash, grupo, nota, creado_por) VALUES (%s,%s,%s,%s,%s)",
                (eid, _hash(token), grupo, nota or None, email), commit=True)
        return token

    def kioscos(self, eid: str) -> list[dict]:
        return self._q("SELECT id, grupo, nota, activo, participantes, creado_por, creado_at::text FROM estudio_kioscos "
                       "WHERE estudio = %s ORDER BY id", (eid,))

    def activar_kiosco(self, eid: str, kid: int, activo: bool):
        self._q("UPDATE estudio_kioscos SET activo=%s WHERE id=%s AND estudio=%s", (activo, kid, eid), commit=True)

    def kiosco(self, token: str) -> dict:
        k = self._q("SELECT k.id, k.estudio, k.grupo, k.activo, e.estado, e.titulo FROM estudio_kioscos k "
                    "JOIN estudio_estudios e ON e.id = k.estudio WHERE k.token_hash = %s", (_hash(token or ''),), one=True)
        if not k or not k['activo']:
            raise NoPermitido('Este equipo ya no está autorizado como kiosco. Pide a quien organiza que lo active de nuevo.')
        if k['estado'] != 'abierto':
            raise NoPermitido('El estudio no está abierto en este momento.')
        return k

    def nuevo_desde_kiosco(self, token: str) -> str:
        """Código nuevo de participante para la siguiente persona en la computadora del kiosco."""
        k = self.kiosco(token)
        [codigo] = self.crear_codigos(k['estudio'], 'participante', k['grupo'], 1, f'kiosco #{k["id"]}', f'kiosco #{k["id"]}')
        self._q("UPDATE estudio_kioscos SET participantes = participantes + 1 WHERE id=%s", (k['id'],), commit=True)
        return codigo

    def activar_codigo(self, codigo: str, activo: bool):
        self._q("UPDATE estudio_codigos SET activo=%s WHERE codigo=%s", (activo, codigo), commit=True)

    def entrar(self, codigo: str, tipo: str) -> dict:
        """Valida un código de acceso → {'codigo', 'estudio', 'grupo', 'spec'}."""
        k = self._q("SELECT k.codigo, k.estudio, k.tipo, k.grupo, k.activo, e.estado FROM estudio_codigos k "
                    "JOIN estudio_estudios e ON e.id = k.estudio WHERE k.codigo = %s",
                    (normalizar_codigo(codigo),), one=True)
        if not k or not k['activo'] or k['tipo'] != tipo:
            raise NoPermitido('Código no válido.')
        if k['estado'] != 'abierto':
            raise NoPermitido('El estudio no está abierto en este momento.')
        return {**k, 'spec': self.spec(k['estudio'])}

    # ── participante ─────────────────────────────────────────────────────────────
    def participante(self, codigo: str) -> dict | None:
        return self._q("SELECT codigo, perfil, asignados, variantes, cierre, consentimiento_at::text, terminado_at::text, "
                       "tutorial_at::text, practicas "
                       "FROM estudio_participantes WHERE codigo=%s", (codigo,), one=True)

    def consentir(self, acceso: dict, perfil: dict) -> dict:
        p = self.participante(acceso['codigo'])
        if p:
            return p
        spec = acceso['spec']
        ids = [e['id'] for e in spec['escenarios']]
        filas = self._q("SELECT e.value #>> '{}' AS esc, count(*) AS n FROM estudio_participantes p "
                        "JOIN estudio_codigos k USING (codigo), jsonb_array_elements(p.asignados) e "
                        "WHERE k.estudio = %s AND k.grupo = %s GROUP BY 1", (acceso['estudio'], acceso['grupo']))
        rng = random.Random()
        asignados = asignar(ids, {f['esc']: f['n'] for f in filas}, int(spec.get('escenarios_por_persona', len(ids))), rng)
        variantes = {}
        for e in spec['escenarios']:
            vs = [v['id'] for v in e.get('variantes') or []]
            if vs and e['id'] in asignados:
                usados = self._q("SELECT p.variantes->>%s AS v, count(*) AS n FROM estudio_participantes p "
                                 "JOIN estudio_codigos k USING (codigo) WHERE k.estudio = %s AND k.grupo = %s "
                                 "AND p.variantes ? %s GROUP BY 1", (e['id'], acceso['estudio'], acceso['grupo'], e['id']))
                variantes[e['id']] = asignar_variante(vs, {u['v']: u['n'] for u in usados}, rng)
        self._q("INSERT INTO estudio_participantes (codigo, perfil, asignados, variantes) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT DO NOTHING",
                (acceso['codigo'], json.dumps(perfil or {}), json.dumps(asignados), json.dumps(variantes)), commit=True)
        return self.participante(acceso['codigo'])

    def intentos(self, codigo: str) -> list[dict]:
        return self._q("SELECT id, escenario, inicio::text, fin::text, confianza FROM estudio_intentos "
                       "WHERE codigo=%s ORDER BY id", (codigo,))

    def iniciar(self, codigo: str, escenario: str) -> dict:
        p = self.participante(codigo)
        if not p or escenario not in p['asignados']:
            raise NoPermitido('Ese escenario no te tocó.')
        self._q("INSERT INTO estudio_intentos (codigo, escenario, variante) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                (codigo, escenario, (p['variantes'] or {}).get(escenario)), commit=True)
        return self._q("SELECT id, escenario, fin::text, preguntas_at::text FROM estudio_intentos WHERE codigo=%s AND escenario=%s",
                       (codigo, escenario), one=True)

    def intento_abierto(self, codigo: str, intento_id: int, para_preguntar: bool = False) -> dict:
        it = self._q("SELECT id, escenario, variante, fin, preguntas_at FROM estudio_intentos WHERE id=%s AND codigo=%s",
                     (intento_id, codigo), one=True)
        if not it:
            raise NoPermitido('Intento no encontrado.')
        if it['fin']:
            raise NoPermitido('Este escenario ya se terminó.')
        if para_preguntar and it['preguntas_at']:
            raise NoPermitido('Ya pasaste a las preguntas: puedes releer la conversación, pero ya no preguntarle al asistente.')
        return it

    def a_preguntas(self, codigo: str, intento_id: int):
        """La persona terminó de conversar y pasa a las preguntas de comprensión (no hay vuelta atrás)."""
        self.intento_abierto(codigo, intento_id)
        if not self._q("SELECT 1 AS x FROM estudio_turnos WHERE intento_id=%s AND respuesta IS NOT NULL LIMIT 1",
                       (intento_id,), one=True):
            raise NoPermitido('Primero hazle al menos una pregunta al asistente.')
        self._q("UPDATE estudio_intentos SET preguntas_at = coalesce(preguntas_at, now()) WHERE id=%s",
                (intento_id,), commit=True)

    def turnos(self, intento_id: int) -> list[dict]:
        return self._q("SELECT id, n, pregunta, respuesta, contexto, error FROM estudio_turnos WHERE intento_id=%s "
                       "ORDER BY n", (intento_id,))

    def guardar_turno(self, intento_id: int, n: int, pregunta: str, out: dict | None, error: str | None,
                      config: dict | None = None) -> int:
        out = out or {}
        dbg = {k: out[k] for k in ('hyde_passage', 'subqueries', 'routes', 'rewrite', 'score_kind') if out.get(k)}
        row = self._q("INSERT INTO estudio_turnos (intento_id, n, pregunta, busqueda, respuesta, contexto, ranking, segundos, "
                      "error, config, busqueda_debug) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                      (intento_id, n, pregunta, out.get('search_query') or None, out.get('answer'),
                       json.dumps(out.get('contexto') or []), json.dumps(out.get('ranking') or []),
                       out.get('seconds'), error, json.dumps(config or {}), json.dumps(dbg, ensure_ascii=False, default=str)),
                      one=True, commit=True)
        return row['id']

    def terminar(self, codigo: str, intento_id: int, spec: dict, respuestas: dict, confianza: int, actuaria: str,
                 detecto: str, detecto_cual: str, comentario: str = ''):
        it = self.intento_abierto(codigo, intento_id)
        esc = escenario_efectivo(next(e for e in spec['escenarios'] if e['id'] == it['escenario']), it['variante'])
        sc = puntuar_comprension(esc, respuestas)
        self._q("UPDATE estudio_intentos SET fin=now(), respuestas=%s, comprension=%s, confianza=%s, actuaria=%s, "
                "detecto=%s, detecto_cual=%s, comentario=%s WHERE id=%s",
                (json.dumps(respuestas), json.dumps(sc), confianza, actuaria, detecto, detecto_cual or None,
                 comentario or None, intento_id),
                commit=True)

    def contar_practica(self, codigo: str, maximo: int) -> bool:
        """Suma una pregunta de práctica si aún no llega al máximo. False = ya no puede."""
        row = self._q("UPDATE estudio_participantes SET practicas = practicas + 1 WHERE codigo=%s AND practicas < %s "
                      "AND tutorial_at IS NULL RETURNING practicas", (codigo, maximo), one=True, commit=True)
        return row is not None

    def tutorial_listo(self, codigo: str):
        self._q("UPDATE estudio_participantes SET tutorial_at = coalesce(tutorial_at, now()) WHERE codigo=%s",
                (codigo,), commit=True)

    def cerrar(self, codigo: str, cierre: dict):
        self._q("UPDATE estudio_participantes SET cierre=%s, terminado_at=now() WHERE codigo=%s",
                (json.dumps(cierre), codigo), commit=True)

    def retirar(self, codigo: str):
        """La persona se retira: se borra todo lo suyo y el código queda inactivo."""
        self._q("DELETE FROM estudio_participantes WHERE codigo=%s", (codigo,), commit=True)
        self.activar_codigo(codigo, False)

    # ── calificación ─────────────────────────────────────────────────────────────
    def _turnos_calificables(self, eid: str) -> list[dict]:
        return self._q(
            "SELECT t.id, t.intento_id, t.n, i.escenario FROM estudio_turnos t JOIN estudio_intentos i ON i.id = t.intento_id "
            "JOIN estudio_codigos k ON k.codigo = i.codigo WHERE k.estudio = %s AND t.respuesta IS NOT NULL AND t.error IS NULL",
            (eid,))

    def _calificaciones(self, eid: str) -> list[dict]:
        return self._q(
            "SELECT c.id, c.turno_id, c.calificador, c.rol, c.veredicto, c.dano, c.error_jurisdiccion, c.cita, c.notas, "
            "c.ts::text FROM estudio_calificaciones c JOIN estudio_codigos k ON k.codigo = c.calificador "
            "WHERE k.estudio = %s ORDER BY c.id", (eid,))

    def siguiente(self, acceso: dict) -> int | None:
        """Turno que le toca a este calificador. Estudiantes: respuestas con menos de 2 calificaciones
        de estudiante (primero las que ya tienen una, para cerrar pares). Experta: las que necesitan
        desempate y aún no tienen su calificación."""
        por_turno: dict[int, list] = {}
        for c in self._calificaciones(acceso['estudio']):
            por_turno.setdefault(c['turno_id'], []).append(c)
        cands = []
        for t in self._turnos_calificables(acceso['estudio']):
            cs = por_turno.get(t['id'], [])
            if any(c['calificador'] == acceso['codigo'] for c in cs):
                continue
            if acceso['grupo'] == 'experto':
                if necesita_experto(cs) and not any(c['rol'] == 'experto' for c in cs):
                    cands.append((0, random.random(), t['id']))
            else:
                n = sum(1 for c in cs if c['rol'] == 'estudiante')
                if n < 2:
                    cands.append((-n, random.random(), t['id']))
        return min(cands)[2] if cands else None

    def para_calificar(self, turno_id: int) -> dict | None:
        t = self._q("SELECT t.id, t.intento_id, t.n, t.pregunta, t.respuesta, t.contexto, i.escenario, i.variante, k.estudio "
                    "FROM estudio_turnos t JOIN estudio_intentos i ON i.id = t.intento_id "
                    "JOIN estudio_codigos k ON k.codigo = i.codigo WHERE t.id = %s", (turno_id,), one=True)
        if not t:
            return None
        previos = self._q("SELECT n, pregunta, respuesta FROM estudio_turnos WHERE intento_id=%s AND n < %s ORDER BY n",
                          (t['intento_id'], t['n']))
        return {**t, 'previos': previos}

    def calificar(self, acceso: dict, turno_id: int, c: dict):
        t = self.para_calificar(turno_id)
        if not t or t['estudio'] != acceso['estudio']:
            raise NoPermitido('Respuesta no encontrada.')
        self._q("INSERT INTO estudio_calificaciones (turno_id, calificador, rol, veredicto, dano, error_jurisdiccion, cita, notas) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (turno_id, calificador) DO UPDATE SET "
                "veredicto=EXCLUDED.veredicto, dano=EXCLUDED.dano, error_jurisdiccion=EXCLUDED.error_jurisdiccion, "
                "cita=EXCLUDED.cita, notas=EXCLUDED.notas, ts=now()",
                (turno_id, acceso['codigo'], acceso['grupo'], c['veredicto'], c['dano'], c['error_jurisdiccion'],
                 c['cita'], c.get('notas') or None), commit=True)

    def progreso_calificador(self, acceso: dict) -> dict:
        hechas = self._q("SELECT count(*) AS n FROM estudio_calificaciones WHERE calificador=%s",
                         (acceso['codigo'],), one=True)['n']
        return {'calificadas': hechas}

    # ── export (seudónimo) ───────────────────────────────────────────────────────
    def export(self, eid: str) -> dict:
        part = self._q("SELECT p.codigo, k.grupo, p.perfil, p.asignados, p.variantes, p.cierre, p.practicas, "
                       "p.tutorial_at::text, p.consentimiento_at::text, "
                       "p.terminado_at::text FROM estudio_participantes p JOIN estudio_codigos k USING (codigo) "
                       "WHERE k.estudio = %s ORDER BY p.consentimiento_at", (eid,))
        intentos = self._q("SELECT i.id, i.codigo, i.escenario, i.variante, i.inicio::text, i.fin::text, i.respuestas, "
                           "i.comprension, i.confianza, i.actuaria, i.detecto, i.detecto_cual, i.preguntas_at::text, i.comentario, "
                           "extract(epoch FROM i.fin - i.inicio)::int AS segundos FROM estudio_intentos i JOIN estudio_codigos k USING (codigo) "
                           "WHERE k.estudio = %s ORDER BY i.id", (eid,))
        turnos = self._q("SELECT t.id, t.intento_id, t.n, t.ts::text, t.pregunta, t.busqueda, t.respuesta, t.contexto, "
                         "t.ranking, t.segundos, t.error, t.config, t.busqueda_debug FROM estudio_turnos t JOIN estudio_intentos i ON i.id = t.intento_id "
                         "JOIN estudio_codigos k ON k.codigo = i.codigo WHERE k.estudio = %s ORDER BY t.id", (eid,))
        return {'estudio': self.obtener(eid), 'participantes': part, 'intentos': intentos, 'turnos': turnos,
                'calificaciones': self._calificaciones(eid)}
