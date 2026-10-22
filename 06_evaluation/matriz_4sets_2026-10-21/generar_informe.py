"""Genera la página del informe (apps/rewrite_lab/static/informes/matriz-2026-10-21.html) a partir de la plantilla y de
estadisticas_matriz.json (la salida de estadisticas_matriz.py) y prompts_sistema.json (obtener_prompts.py). Se sirve en /benchmark/informe/matriz-2026-10-21.

    python generar_informe.py"""
import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
datos = json.loads((AQUI / 'estadisticas_matriz.json').read_text())
prompts = json.loads((AQUI / 'prompts_sistema.json').read_text())   # obtener_prompts.py
html = (AQUI / 'informe_plantilla.html').read_text().replace('__DATA__', json.dumps(datos, ensure_ascii=False))
html = html.replace('__PROMPTS__', json.dumps(prompts, ensure_ascii=False).replace('</', '<\\/'))
destino = AQUI.parents[1] / 'apps' / 'rewrite_lab' / 'static' / 'informes' / 'matriz-2026-10-21.html'
destino.parent.mkdir(exist_ok=True)
destino.write_text(html)
print('escrito', destino)
