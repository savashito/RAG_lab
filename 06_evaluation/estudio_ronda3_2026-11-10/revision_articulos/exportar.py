"""
Exporta lo que necesita la revisión de artículos (clasificar.py) a una carpeta, para copiarla al clúster:

    articulos.jsonl   un artículo por línea de los 5 códigos penales: {codigo, ruta, num, texto}
    catalogo.json     la copia de trabajo del catálogo de casos (la que se edita en /catalogo), con su md5

Corre en prod (lee la base; no escribe nada):
    cd ~/apps/RAG_lab && set -a && . apps/rewrite_lab/.env && set +a && \
      .venv/bin/python 06_evaluation/estudio_ronda3_2026-11-10/revision_articulos/exportar.py ~/revision_articulos

Es texto de ley y el catálogo: no hay datos de participantes.
"""
from __future__ import annotations

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


def main(salida: Path) -> None:
    salida.mkdir(parents=True, exist_ok=True)
    articulos: dict[tuple[str, str], list[str]] = {}
    with connect() as c, c.cursor() as cur:
        for codigo, source in CODIGOS.items():
            cur.execute(f'SELECT hierarchy, text FROM {TABLE} WHERE source = %s ORDER BY position, part', (source,))
            for ruta, texto in cur.fetchall():
                k = texto.find(ruta)
                articulos.setdefault((codigo, ruta), []).append(texto[k + len(ruta):].strip() if k >= 0 else texto)
        cur.execute('SELECT doc FROM consulta_catalogo WHERE id = 1')
        doc = cur.fetchone()[0]
    with open(salida / 'articulos.jsonl', 'w') as f:
        for (codigo, ruta), partes in articulos.items():
            ultimo = ruta.split(' > ')[-1]
            num = ultimo[len('Artículo '):] if ultimo.startswith('Artículo ') else ''
            f.write(json.dumps({'codigo': codigo, 'ruta': ruta, 'num': num, 'texto': '\n\n'.join(partes)},
                               ensure_ascii=False) + '\n')
    md5 = hashlib.md5(json.dumps(doc, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    (salida / 'catalogo.json').write_text(json.dumps({'md5': md5, 'doc': doc}, ensure_ascii=False, indent=1))
    print(f'{len(articulos)} artículos, catálogo {md5[:8]} → {salida}')


if __name__ == '__main__':
    main(Path(sys.argv[1] if len(sys.argv) > 1 else 'data'))
