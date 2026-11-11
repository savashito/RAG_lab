"""
Exporta lo que necesita la revisión de artículos (clasificar.py) a una carpeta, para copiarla al clúster:

    articulos.jsonl   un artículo por línea: {codigo, materia, ruta, num, texto}. `codigo` es la clave de la ley
                      (cdmx, cnpp, cc_cdmx…); `materia` dice con qué prompt la lee clasificar.py (penal o familiar)
    catalogo.json     la copia de trabajo del catálogo de casos (la que se edita en /catalogo), con su md5

Corre en prod (lee la base; no escribe nada):
    cd ~/apps/RAG_lab && set -a && . apps/rewrite_lab/.env && set +a && \
      .venv/bin/python 06_evaluation/estudio_ronda3_2026-11-10/revision_articulos/exportar.py ~/revision_articulos
    … exportar.py ~/revision_leyes --fuentes leyes     # las otras leyes penales y las de familia (también apagadas)

Los libros y manuales no se exportan: no tienen artículos que una regla pueda citar.

Es texto de ley y el catálogo: no hay datos de participantes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

RAIZ = Path(os.environ.get('RAG_LAB_RAIZ') or Path(__file__).resolve().parents[3])   # raíz de labs/
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'apps' / 'rewrite_lab'))

from shared.db import connect  # noqa: E402
from consulta.catalogo import CODIGOS  # noqa: E402

TABLE = 'sistema_penal__qwen06__legal'

# Las demás leyes con artículos de los temas derecho_penal_mexicano y derecho_familiar (se buscan por el inicio del
# nombre del documento; las apagadas en /ingesta también entran). clave → (inicio del nombre, materia)
LEYES = {
    'cnpp': ('Código Nacional de Procedimientos Penales', 'penal'),
    'ley_victimas': ('Ley General de Víctimas', 'penal'),
    'ley_extorsion': ('Ley General para Prevenir, Investigar y Sancionar Delitos en Materia de Extorsi', 'penal'),
    'ley_secuestro': ('Ley General para Delitos en Materia de Secuestro', 'penal'),
    'lfcdo': ('Ley Federal Contra la Delincuencia Organizada', 'penal'),
    'lfra': ('Ley Federal de Responsabilidad Ambiental', 'penal'),
    'lgamvlv': ('Ley General de Acceso de las Mujeres a una Vida Libre de Violencias', 'penal'),
    'lgeepa': ('LEY GENERAL DEL EQUILIBRIO ECOLÓGICO', 'penal'),
    'cc_cdmx': ('Código Civil para el Distrito Federal', 'familiar'),
    'cpc_cdmx': ('Código de Procedimientos Civiles para el Distrito Federal', 'familiar'),
    'cnpcf': ('Código Nacional de Procedimientos Civiles y Familiares', 'familiar'),
}


def main(salida: Path, fuentes: str) -> None:
    salida.mkdir(parents=True, exist_ok=True)
    articulos: dict[tuple[str, str], list[str]] = {}
    materia: dict[str, str] = {}
    with connect() as c, c.cursor() as cur:
        consultas = []
        if fuentes in ('codigos', 'todas'):
            consultas += [(codigo, 'penal', 'source = %s', source) for codigo, source in CODIGOS.items()]
        if fuentes in ('leyes', 'todas'):
            consultas += [(codigo, m, 'source LIKE %s', inicio + '%') for codigo, (inicio, m) in LEYES.items()]
        for codigo, m, donde, valor in consultas:
            materia[codigo] = m
            cur.execute(f'SELECT count(DISTINCT source) FROM {TABLE} WHERE {donde}', (valor,))
            assert cur.fetchone()[0] == 1, f'{codigo}: el nombre no da exactamente un documento'
            cur.execute(f'SELECT hierarchy, text FROM {TABLE} WHERE {donde} ORDER BY position, part', (valor,))
            for ruta, texto in cur.fetchall():
                k = texto.find(ruta)
                articulos.setdefault((codigo, ruta), []).append(texto[k + len(ruta):].strip() if k >= 0 else texto)
        cur.execute('SELECT doc FROM consulta_catalogo WHERE id = 1')
        doc = cur.fetchone()[0]
    with open(salida / 'articulos.jsonl', 'w') as f:
        for (codigo, ruta), partes in articulos.items():
            ultimo = ruta.split(' > ')[-1]
            num = ultimo[len('Artículo '):] if ultimo.startswith('Artículo ') else ''
            f.write(json.dumps({'codigo': codigo, 'materia': materia[codigo], 'ruta': ruta, 'num': num, 'texto': '\n\n'.join(partes)},
                               ensure_ascii=False) + '\n')
    md5 = hashlib.md5(json.dumps(doc, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    (salida / 'catalogo.json').write_text(json.dumps({'md5': md5, 'doc': doc}, ensure_ascii=False, indent=1))
    for codigo in materia:
        print(f'  {codigo}: {sum(1 for c, _ in articulos if c == codigo)}')
    print(f'{len(articulos)} artículos, catálogo {md5[:8]} → {salida}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('salida', type=Path, nargs='?', default=Path('data'))
    ap.add_argument('--fuentes', choices=['codigos', 'leyes', 'todas'], default='codigos')
    a = ap.parse_args()
    main(a.salida, a.fuentes)
