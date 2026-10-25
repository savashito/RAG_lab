"""Compara versiones de la regex pregunta_de_lugar contra el set de referencia pide_lugar_etiquetas (lo que dijo Gemma),
sin volver a llamar a Gemma. Cada versión es un archivo jurisdiction_gate.py.
    python comparar.py VIEJA.py [NUEVA.py]     (NUEVA por omisión: el de la app)
Imprime, por versión: cuántas peticiones encuentra / se le escapan / falsos positivos; y entre las dos: qué arregla la
nueva y qué rompe (con la frase)."""
import sys, os, importlib.util
from collections import Counter
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
os.chdir('/home/tlacua/apps/RAG_lab/apps/rewrite_lab')
from dotenv import load_dotenv; load_dotenv('.env')
from shared.db import connect

def cargar(ruta, nombre):
    s = importlib.util.spec_from_file_location(nombre, ruta); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
vieja = cargar(sys.argv[1], 'vieja')
nueva = cargar(sys.argv[2] if len(sys.argv) > 2 else '/home/tlacua/apps/RAG_lab/apps/rewrite_lab/jurisdiction_gate.py', 'nueva')
with connect() as c, c.cursor() as cur:
    cur.execute('SELECT respuesta, fuente, gemma_pide, gemma_frase FROM pide_lugar_etiquetas WHERE gemma_pide IS NOT NULL')
    filas = cur.fetchall()
print(f'Set de referencia: {len(filas)} respuestas con etiqueta de Gemma · Gemma dice que piden el lugar: {sum(f[2] for f in filas)}')
res = {}
for nombre, m in (('vieja', vieja), ('nueva', nueva)):
    t = Counter()
    for r, fuente, g, _ in filas:
        x = m.pregunta_de_lugar(r) is not None
        t['encuentra' if g and x else 'se escapa' if g else 'falso positivo' if x else 'bien: nada'] += 1
    res[nombre] = t
    pide = t['encuentra'] + t['se escapa']
    print(f'  {nombre}: encuentra {t["encuentra"]} de {pide} ({100 * t["encuentra"] / pide:.1f} %) · se escapan {t["se escapa"]} · '
          f'falsos positivos {t["falso positivo"]} de {len(filas) - pide} ({100 * t["falso positivo"] / (len(filas) - pide):.1f} %)')
arregla, rompe, quedan_escapan, quedan_sobran = [], [], [], []
for r, fuente, g, frase in filas:
    a, b = vieja.pregunta_de_lugar(r), nueva.pregunta_de_lugar(r)
    ok_a, ok_b = (a is not None) == g, (b is not None) == g
    if ok_b and not ok_a: arregla.append(frase if g else a)
    if ok_a and not ok_b: rompe.append(frase if g else b)
    if not ok_b: (quedan_escapan if g else quedan_sobran).append(frase if g else b)
print(f'\nLa nueva arregla {len(arregla)} y rompe {len(rompe)}.')
print('\nRompe:'); [print('  -', x) for x in rompe[:30]]
print('\nSiguen escapándose con la nueva:'); [print('  -', x) for x in quedan_escapan[:40]]
print('\nFalsos positivos que siguen con la nueva:'); [print('  -', x) for x in quedan_sobran[:40]]
