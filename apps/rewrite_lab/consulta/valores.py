"""
Valores de referencia: cantidades en pesos que cambian cada año (la UMA) y que los artículos citan como
«de trescientas a setecientas veces la Unidad de Medida y Actualización».

Viven en la base (tabla valores_referencia), con historial: un valor nuevo es una fila nueva y la anterior se queda,
para saber con qué valor se orientó cada conversación. Se editan en /catalogo (pestaña Valores) con el mismo permiso
que el catálogo. Una fila puede decir `igual_a: uma` en vez de un valor: la Unidad de Cuenta de la CDMX quedó abrogada
y se calcula con la UMA vigente.

Las cuentas las hace este código (convertir), no el LLM: el LLM de la app se equivoca al multiplicar. Los «días multa»
no se convierten: dependen de los ingresos de la persona sentenciada.
"""
from __future__ import annotations

import datetime as dt
import re
import unicodedata
from typing import Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

SCHEMA = """
CREATE TABLE IF NOT EXISTS valores_referencia (
    id serial PRIMARY KEY, clave text NOT NULL, nombre text NOT NULL, valor numeric, igual_a text,
    vigente_desde date NOT NULL, fuente text NOT NULL, url text, nota text, por text, creado timestamptz DEFAULT now());
"""

# Lo que se carga si la tabla está vacía (revisado el 2026-11-12 en las publicaciones oficiales).
INICIALES = [
    {'clave': 'uma', 'nombre': 'Unidad de Medida y Actualización (UMA)', 'valor': 117.31, 'vigente_desde': '2026-02-01',
     'fuente': 'INEGI, comunicado de prensa 1/26 (8 de enero de 2026); publicada en el DOF el 9 de enero de 2026',
     'url': 'https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/uma/uma2026.pdf',
     'nota': 'Valor diario. Mensual $3,566.22; anual $42,794.64. Se actualiza cada año y entra en vigor el 1 de febrero.'},
    {'clave': 'uc_cdmx', 'nombre': 'Unidad de Cuenta de la Ciudad de México', 'igual_a': 'uma', 'vigente_desde': '2017-02-01',
     'fuente': 'Código Fiscal de la Ciudad de México, artículo vigésimo quinto transitorio del decreto del 20 de diciembre '
               'de 2016 (p. 397 de la edición 2026)',
     'url': 'https://cdmxassets.s3.us-east-1.amazonaws.com/media/files-pdf/marco_normativo2026/01_CODIGO_FISCAL_2026.pdf',
     'nota': 'La Ley de Unidad de Cuenta de la Ciudad de México quedó abrogada al publicarse la UMA 2017; los artículos '
             'que todavía dicen «Unidad de Cuenta» se calculan con la UMA. Pendiente: que Karen lo confirme.'},
    {'clave': 'salario_minimo', 'nombre': 'Salario mínimo (como unidad de cuenta)', 'igual_a': 'uma',
     'vigente_desde': '2016-01-28',
     'fuente': 'Decreto de desindexación del salario mínimo (reforma constitucional, DOF 27 de enero de 2016), '
               'artículo tercero transitorio',
     'nota': 'Las menciones al salario mínimo como unidad de cuenta en las leyes se entienden hechas a la UMA. No vale '
             'para los días multa ni para salarios. Pendiente: que Karen lo confirme.'},
]
AVISO_DIAS = 365     # un valor propio con más de un año se marca para revisar
MAX_CONVERSIONES = 30


# ── leer ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def vigentes(filas: list[dict], hoy: dt.date | None = None) -> dict[str, dict]:
    """Filas de la tabla → {clave: la fila vigente hoy}, con `valor` resuelto (`igual_a`) y `revisar` si el valor
    propio tiene más de AVISO_DIAS."""
    hoy = hoy or dt.date.today()
    out: dict[str, dict] = {}
    for f in sorted(filas, key=lambda f: (str(f['vigente_desde']), f.get('id') or 0)):
        if dt.date.fromisoformat(str(f['vigente_desde'])[:10]) <= hoy:
            out[f['clave']] = dict(f)
    for f in out.values():
        base = out.get(f.get('igual_a') or '') if f.get('igual_a') else f
        f['valor'] = float(base['valor']) if base and base.get('valor') is not None else None
        desde = dt.date.fromisoformat(str((base or f)['vigente_desde'])[:10])
        f['revisar'] = (hoy - desde).days > AVISO_DIAS
    return out


# ── números escritos en español («ciento cincuenta», «un mil», «2,000») ─────────────────────────────────────────────
_U = {'un': 1, 'uno': 1, 'una': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8,
      'nueve': 9, 'diez': 10, 'once': 11, 'doce': 12, 'trece': 13, 'catorce': 14, 'quince': 15, 'dieciseis': 16,
      'diecisiete': 17, 'dieciocho': 18, 'diecinueve': 19, 'veinte': 20, 'veintiun': 21, 'veintiuno': 21,
      'veintiuna': 21, 'veintidos': 22, 'veintitres': 23, 'veinticuatro': 24, 'veinticinco': 25, 'veintiseis': 26,
      'veintisiete': 27, 'veintiocho': 28, 'veintinueve': 29, 'treinta': 30, 'cuarenta': 40, 'cincuenta': 50,
      'sesenta': 60, 'setenta': 70, 'ochenta': 80, 'noventa': 90, 'cien': 100, 'ciento': 100}
for _r, _n in (('doscient', 200), ('trescient', 300), ('cuatrocient', 400), ('quinient', 500), ('seiscient', 600),
               ('setecient', 700), ('ochocient', 800), ('novecient', 900)):
    _U[_r + 'os'] = _U[_r + 'as'] = _n
_PALABRAS = set(_U) | {'mil', 'y'}


def _sin_acentos(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')


def numero(tokens: list[str]) -> int | None:
    """['ciento', 'cincuenta'] → 150; ['un', 'mil'] → 1000; ['2,000'] → 2000."""
    if len(tokens) == 1 and re.fullmatch(r'\d[\d,.]*', tokens[0]):
        return int(re.sub(r'[,.]', '', tokens[0]))
    total, actual = 0, 0
    for t in tokens:
        if t == 'y':
            continue
        if t == 'mil':
            total += (actual or 1) * 1000
            actual = 0
        elif t in _U:
            actual += _U[t]
        else:
            return None
    return total + actual or None


def _numero_al_final(texto: str) -> tuple[int | None, str]:
    """El número con que termina `texto` (palabras o cifras) → (número, lo que queda antes)."""
    tokens = texto.split()
    i = len(tokens)
    if i and re.fullmatch(r'\d[\d,.]*', tokens[-1]):
        return numero(tokens[-1:]), ' '.join(tokens[:-1])
    while i and tokens[i - 1] in _PALABRAS:
        i -= 1
    while i < len(tokens) and tokens[i] == 'y':     # «… y» suelto no es parte del número
        i += 1
    return (numero(tokens[i:]) if i < len(tokens) else None), ' '.join(tokens[:i])


_UNIDAD = re.compile(r'unidad(?:es)? de cuenta(?: de la ciudad de mexico)?|unidad(?:es)? de medida y actualizacion'
                     r'|\buma\b|salarios? minimos?(?: generales?)?')
_ENLACE = re.compile(r'\s*(?:veces|dias de)?\s*(?:el\s+)?(?:importe\s+del\s+)?(?:valor\s+)?(?:diario\s+)?(?:de\s+)?'
                     r'(?:la\s+|las\s+|el\s+|los\s+)?$')


def _clave(unidad: str) -> str:
    return 'uc_cdmx' if 'cuenta' in unidad else 'salario_minimo' if 'salario' in unidad else 'uma'


def menciones(texto: str) -> list[tuple[int | None, int, str]]:
    """Cantidades en unidades que cita un artículo → [(desde o None, hasta, clave)]."""
    t = re.sub(r'[*_]+', ' ', _sin_acentos(texto))
    t = re.sub(r'\s+', ' ', t)
    out = []
    for m in _UNIDAD.finditer(t):
        antes = _ENLACE.sub('', t[max(0, m.start() - 120):m.start()])
        hasta, resto = _numero_al_final(antes)
        if not hasta:
            continue
        desde = None
        if resto.endswith(' a'):
            desde, _ = _numero_al_final(resto[:-2])
        out.append((desde, hasta, _clave(m.group(0))))
    return out


def _pesos(x: float) -> str:
    return f'${x:,.2f}'


def bloque(textos: list[str], vals: dict[str, dict]) -> tuple[str, list[str]]:
    """Los textos de los artículos que entran a la orientación → (el bloque para el prompt, las conversiones).
    Vacío si ningún artículo cita una unidad ni días multa."""
    vistas, conv = set(), []
    for x in textos:
        for desde, hasta, clave in menciones(x):
            v = (vals.get(clave) or {}).get('valor')
            if v is None or (desde, hasta, clave) in vistas:
                continue
            vistas.add((desde, hasta, clave))
            nombre = vals[clave]['nombre']
            conv.append(f'{desde:,} a {hasta:,} × {nombre} = {_pesos(desde * v)} a {_pesos(hasta * v)}' if desde
                        else f'{hasta:,} × {nombre} = {_pesos(hasta * v)}')
    dias_multa = any(re.search(r'd[ií]as?[ -]multa', x, re.I) for x in textos)
    if not conv and not dias_multa:
        return '', []
    lineas = ['VALORES VIGENTES (los calcula el sistema; usa estos montos en pesos y no hagas tú las cuentas):']
    for clave in dict.fromkeys(c for _, _, c in vistas):
        f = vals[clave]
        base = vals.get(f.get('igual_a') or '') or f
        igual = f' (se calcula con {base["nombre"]})' if base is not f else ''
        lineas.append(f'- {f["nombre"]}: {_pesos(f["valor"])} diarios{igual}, vigente desde {str(base["vigente_desde"])[:10]}.')
    lineas += [f'- {c}' for c in conv[:MAX_CONVERSIONES]]
    if dias_multa:
        lineas.append('- Los «días multa» dependen de los ingresos de la persona sentenciada: no los conviertas a pesos.')
    return '\n'.join(lineas), conv


# ── tabla y API ──────────────────────────────────────────────────────────────────────────────────────────────────
COLUMNAS = ('id', 'clave', 'nombre', 'valor', 'igual_a', 'vigente_desde', 'fuente', 'url', 'nota', 'por', 'creado')


class Valores:
    def __init__(self, *, connect: Callable, current_email: Callable, can_edit: Callable):
        self.connect, self.current_email, self.can_edit = connect, current_email, can_edit
        with connect() as c, c.cursor() as cur:
            cur.execute(SCHEMA)
            cur.execute("SELECT 1 FROM valores_referencia LIMIT 1")
            if not cur.fetchone():
                for f in INICIALES:
                    self._insertar(cur, f, 'valores iniciales (Claude, 2026-11-12)')
            c.commit()
        self.router = self._make_router()

    def _insertar(self, cur, f: dict, por: str):
        cur.execute("INSERT INTO valores_referencia (clave, nombre, valor, igual_a, vigente_desde, fuente, url, nota, por) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (f['clave'], f['nombre'], f.get('valor'), f.get('igual_a'), f['vigente_desde'], f['fuente'],
                     f.get('url'), f.get('nota'), por))

    def filas(self) -> list[dict]:
        with self.connect() as c, c.cursor() as cur:
            cur.execute(f"SELECT {', '.join(COLUMNAS)} FROM valores_referencia ORDER BY clave, vigente_desde, id")
            return [dict(zip(COLUMNAS, r)) for r in cur.fetchall()]

    def vigentes(self) -> dict[str, dict]:
        return vigentes(self.filas())

    @staticmethod
    def validar(f: dict, claves: set[str]) -> dict:
        f = {k: (v.strip() if isinstance(v, str) else v) for k, v in (f or {}).items()}
        if not re.fullmatch(r'[a-z][a-z0-9_]*', f.get('clave') or ''):
            raise ValueError('La clave va en minúsculas con guion bajo (p. ej. uma).')
        if not f.get('nombre') or not f.get('fuente'):
            raise ValueError('Faltan el nombre o la fuente.')
        try:
            dt.date.fromisoformat(f.get('vigente_desde') or '')
        except ValueError:
            raise ValueError('La fecha «vigente desde» va como AAAA-MM-DD.')
        if f.get('igual_a'):
            if f['igual_a'] not in claves or f['igual_a'] == f['clave']:
                raise ValueError('«Igual a» debe ser la clave de otro valor.')
            f['valor'] = None
        else:
            try:
                f['valor'] = float(str(f.get('valor')).replace(',', '').replace('$', ''))
            except ValueError:
                raise ValueError('El valor debe ser un número en pesos.')
            if f['valor'] <= 0:
                raise ValueError('El valor debe ser mayor que cero.')
        return f

    def _make_router(self) -> APIRouter:
        r = APIRouter()

        @r.get('/api/valores')
        def obtener():
            filas = self.filas()
            return {'vigentes': vigentes(filas), 'historial': filas}

        @r.post('/api/valores')
        async def agregar(request: Request):
            email = self.current_email(request)
            if not self.can_edit(email):
                return JSONResponse({'error': 'No tienes permiso para editar los valores.'}, status_code=403)
            try:
                f = self.validar(await request.json(), {x['clave'] for x in self.filas()})
            except ValueError as e:
                return JSONResponse({'error': str(e)}, status_code=400)
            with self.connect() as c, c.cursor() as cur:
                self._insertar(cur, f, email)
                c.commit()
            return obtener()
        return r
