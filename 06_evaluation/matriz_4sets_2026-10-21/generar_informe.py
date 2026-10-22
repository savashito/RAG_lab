"""Genera la página del informe (apps/rewrite_lab/static/informes/matriz-2026-10-21.html) a partir de la plantilla y de
estadisticas_matriz.json (la salida de estadisticas_matriz.py). Se sirve en /benchmark/informe/matriz-2026-10-21.

    python generar_informe.py"""
import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
datos = json.loads((AQUI / 'estadisticas_matriz.json').read_text())
html = (AQUI / 'informe_plantilla.html').read_text().replace('__DATA__', json.dumps(datos, ensure_ascii=False))
destino = AQUI.parents[1] / 'apps' / 'rewrite_lab' / 'static' / 'informes' / 'matriz-2026-10-21.html'
destino.parent.mkdir(exist_ok=True)
destino.write_text(html)
print('escrito', destino)
