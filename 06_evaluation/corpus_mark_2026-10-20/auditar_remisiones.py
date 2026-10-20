"""Revisión automática del detector de remisiones sobre los 5 códigos penales del corpus (solo lectura): cuántas
remisiones seguiría, y cuántas apuntan a un artículo que NO existe en ese código (casi siempre errores de detección).
Se corre en el servidor:  cd ~/apps/RAG_lab/apps/rewrite_lab && ~/.local/bin/uv run python <este script>"""
import collections, random, re, sys
sys.path[:0] = ['/home/tlacua/apps/RAG_lab', '/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/tmp/remaudit']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
import remisiones as rm
SRC = ['Código Penal del Estado de México.md', 'Código Penal de la Ciudad de México.md', 'Código Penal Federal.md',
       'Código Penal del Estado de Querétaro.md', 'Código PENALEM.md']
key = lambda a: re.sub(r'[^0-9a-záéíóúñ]', '', (a or '').lower().replace('quáter', 'quater').replace('°', 'o').replace('º', 'o'))
with connect() as c, c.cursor() as cur:
    cur.execute("SELECT source, title, text FROM sistema_penal__qwen06__legal WHERE source = ANY(%s) AND title LIKE 'Artículo%%' ORDER BY source, position", (SRC,))
    rows = cur.fetchall()
existe = collections.defaultdict(set)
for s, t, _ in rows:
    existe[s].add(key(t.replace('Artículo', '')))
    existe[s].add(key(re.sub(r'o$', '', t.replace('Artículo', '').strip())))
stats = collections.Counter(); malos = []; rechazos = collections.Counter(); materias = collections.Counter()
for s, t, txt in rows:
    for r in rm.detectar(txt):
        if r['rechazo']:
            rechazos[r['rechazo']] += 1; continue
        if r['tipo'] == 'relativa':
            stats['relativa'] += 1; continue
        stats['numerada'] += 1; materias[r['materia']] += 1
        k = key(r['articulo'])
        if k in existe[s] or k.rstrip('o') in existe[s]:
            stats['existe'] += 1
        else:
            stats['NO existe'] += 1; malos.append((s.replace('.md', '')[-26:], t, r['texto'], r['ambito']))
print(f'{len(rows)} artículos · remisiones a seguir: {stats["numerada"]} numeradas ({stats["existe"]} apuntan a un artículo que existe, '
      f'{stats["NO existe"]} a uno que NO) + {stats["relativa"]} relativas')
print('materia de las numeradas:', dict(materias))
print('rechazadas:', dict(rechazos))
random.seed(1)
print('\nmuestra de las que apuntan a un artículo inexistente:')
for x in random.sample(malos, min(25, len(malos))):
    print('  ', x)
