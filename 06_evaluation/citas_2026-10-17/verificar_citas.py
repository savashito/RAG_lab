"""Verificación de citas (sin juez): para cada artículo que cita una respuesta del asistente, ¿existe en el corpus?,
¿venía en el CONTEXTO recuperado?, ¿está derogado? Solo lectura.

  python verificar_citas.py estudio            → respuestas del estudio de usuarios (sin las 3 pruebas)
  python verificar_citas.py bench 37 38 ...    → corridas del benchmark (respuesta y chunks del artefacto)

Clasificación de cada cita (ley, artículo):
  en_contexto       el artículo llegó al contexto del LLM → respaldada por lo recuperado
  fuera_de_contexto existe en el corpus pero NO venía en el contexto → el modelo la sacó de su memoria
                    (el prompt pide «solo con el contexto»); puede ser correcta, pero no está fundamentada
  atribucion_cruzada no venía en el contexto con ESA ley, pero el mismo número de artículo sí venía con OTRA ley
                    (p. ej. «art. 269 del Código Penal de la CDMX» cuando el 269 del contexto es del Edomex)
  no_existe         la ley está en el corpus pero ese artículo no → inventado o mal numerado (revisar a mano)
  ley_fuera         la ley no está en el corpus (no se puede verificar)
  + derogado        el texto del artículo en el corpus dice «se deroga» / «derogado»
Emparejamiento artículo→ley: ver `ley_de`. Sin ley identificable → `sin_ley` (no se clasifica). Salida: JSON + muestra para revisión."""
import sys, json, re, collections, random
sys.path[:0] = ['/home/tlacua/apps/RAG_lab/apps/rewrite_lab', '/home/tlacua/apps/RAG_lab']
from dotenv import load_dotenv; load_dotenv('/home/tlacua/apps/RAG_lab/apps/rewrite_lab/.env')
from shared.db import connect
from shared.code_routes import codes_in, short_label
from bench import resolve_gold
# Como bench._ART_LIST_RE, más sufijos latinos que usan el CPF y la CDMX (199 Octies, 211 Quinquies 1, 343 Ter 2…).
_SUF = (r'(?:\s*(?:o\b|bis\b|ter\b|qu[aá]ter\b|quintus\b|quinquies\b|sextus\b|sexies\b|septimus\b|septies\b|'
        r'octies\b|nonies\b|decies\b))?(?:\s+\d\b)?')
_ART_LIST_RE = re.compile(r'(?i)\bart(?:[íi]culos?|s?\.)\s*(\d+' + _SUF + r'(?:\s*(?:,|\by\b)\s*\d+' + _SUF + r')*)')
_ART_ONE_RE = re.compile(r'(?i)\d+' + _SUF)
# «del citado código», «del código local», «de ese ordenamiento»: la ley no se puede saber con certeza.
AMBIGUA = re.compile(r'(?i)^[\s*_,]*(?:,?\s*(?:fracci[oó]n|frac\.|apartado|inciso|p[aá]rrafo)[^.;()\n]{0,40}?)?[\s,*_]*(?:del|de la|de este|de ese)\s+(?:citad[oa]|mism[oa]|c[oó]digo local|c[oó]digo penal local|ordenamiento|ley local)')
# «Artículo 12 de *Lecciones de Derecho Penal*»: «de …» que no es una ley → la cita no es de una ley del corpus.
DE_ALGO = re.compile(r'(?i)^[\s*_,]*(?:,?\s*(?:fracci[oó]n|frac\.|apartado|inciso|p[aá]rrafo)[^.;()\n]{0,40}?)?[\s,*_]*(?:del|de la|de los|de)\s+[*_]*[A-ZÁÉÍÓÚ]')
TABLE = 'sistema_penal__qwen06__legal'
PRUEBAS = ['NGSX-GGPH', 'K9TQ-6P86', 'FYJ2-VS7R']
# Entre el artículo y la ley que lo sigue: «del/de la …» (quizá tras fracción/párrafo/inciso) o solo una coma
# («Art. 20, frac. I, CNPP»; «Art. 107, Código Penal CDMX»); hasta 45 caracteres del nombre antes del alias.
CONECTOR = re.compile(r'(?i)^[\s*_]*(?:,?\s*(?:fracci[oó]n|frac\.|apartado|inciso|p[aá]rrafo)[^.;()\n]{0,40}?)?[\s,*_]*(?:(?:del|de la|de los|de)\s[^.;()\n]{0,45}|,\s*[*_]*(?:[^.;()\n]{0,45}\s)?|\s*[*_]*)$')
FIN_ORACION = re.compile(r'(?<!\bart)(?<!\barts)(?<!\bfrac)(?<!\bNo)[.;]\**\s+(?=[*_¿(]*[A-ZÁÉÍÓÚ])')
COMPARA = re.compile(r'(?i)(al igual que|a diferencia de|igual que|como en|similar a|que en)\W+(?:en\s+)?(?:la|el)?\s*$')
DEROG = re.compile(r'(?i)^\W*(se deroga|derogad[oa])\b')

def ley_en_tabla(texto, ini_l, pos):
    """Tabla «| Concepto | Ciudad de México | Querétaro |»: la ley de una celda es la del encabezado de su columna; si
    el encabezado no nombra una ley, la de la propia celda; si no, None (sin ley identificable)."""
    lineas = texto[:ini_l].split('\n')
    k = len(lineas) - 2   # retrocede hasta la primera fila de la tabla
    while k >= 0 and lineas[k].lstrip().startswith('|'):
        k -= 1
    encabezado = lineas[k + 1] if k + 1 < len(lineas) - 1 else texto[ini_l:texto.find('\n', ini_l)]
    col = texto[ini_l:pos].count('|') - 1
    celdas = [c for c in encabezado.strip().strip('|').split('|')]
    if 0 <= col < len(celdas):
        h = codes_in(celdas[col])
        if h:
            return h[0]
    fin_c = texto.find('|', pos)
    celda = texto[texto.rfind('|', 0, pos) + 1:fin_c if fin_c > 0 else len(texto)]
    h = codes_in(celda)
    return h[0] if h else None


def ley_de(texto, m):
    """Ley de la cita `m`: (1) la nombrada justo después («art. 179 del Código Penal de la CDMX», «Artículo 2,
    fracción IV, de la Ley General…»: ≤ 40 caracteres de separación, misma línea); si no, (2) la última nombrada
    antes en la MISMA línea («**Código Penal de Querétaro:** Artículos 167 Bis y 167 Ter»); si no, (3) la primera
    después en la misma línea; si no, None (sin ley identificable: no se clasifica)."""
    ini_l = texto.rfind('\n', 0, m.start()) + 1
    fin_l = texto.find('\n', m.end()); fin_l = len(texto) if fin_l < 0 else fin_l
    linea = texto[ini_l:fin_l]
    if linea.lstrip().startswith('|'):   # tabla markdown: la ley es la del encabezado de la columna
        return ley_en_tabla(texto, ini_l, m.start())
    tramo = texto[m.end():min(fin_l, m.end() + 200)]
    if AMBIGUA.match(tramo):
        return None
    despues = codes_in(tramo)
    if despues and CONECTOR.match(tramo[:despues[0]['start']]):
        return despues[0]
    if DE_ALGO.match(tramo) and not codes_in(tramo[:90]):
        return None
    linea_antes = texto[ini_l:m.start()]
    # En prosa una «línea» es un párrafo entero: solo cuenta la oración del artículo («art. 5» no corta).
    cortes = [x.end() for x in FIN_ORACION.finditer(linea_antes)]
    if cortes:
        linea_antes = linea_antes[cortes[-1]:]
    antes_l = codes_in(linea_antes)
    if antes_l:
        h = antes_l[-1]
        # «Al igual que en la CDMX, el Artículo 201…»: esa ley es la de la comparación, no la del artículo.
        return None if COMPARA.search(linea_antes[max(0, h['start'] - 30):h['start']]) else h
    if despues and not FIN_ORACION.search(tramo[:despues[0]['start']]):   # misma oración
        return None if COMPARA.search(tramo[:despues[0]['start']]) else despues[0]
    # Sin ley en la misma línea no se adivina por el párrafo: en respuestas comparativas la ley del párrafo suele ser
    # la de la comparación («Al igual que en la CDMX, el Artículo 188…» dentro de la sección de Querétaro).
    return None


def citas(texto):
    """[(source, label_ley, artículo, fragmento)] de una respuesta."""
    out, seen = [], set()
    for m in _ART_LIST_RE.finditer(texto or ''):
        ley = ley_de(texto, m)
        for a in _ART_ONE_RE.findall(m.group(1)):
            a = re.sub(r'\s+', ' ', a.strip())
            k = (ley['source'] if ley else None, a.lower())
            if k in seen: continue
            seen.add(k)
            out.append((ley['source'] if ley else None, ley['label'] if ley else None, a,
                        texto[max(0, m.start() - 60):m.end() + 90].replace('\n', ' ')))
    return out

def clasificar(cur, filas):
    """filas: [(origen, respuesta, ids_contexto)] → lista de citas clasificadas."""
    fuentes = {r[0] for r in (cur.execute(f"SELECT DISTINCT source FROM {TABLE}") or cur.fetchall())}
    cache, res, art_ctx = {}, [], {}
    todos = {i for _, _, ctx in filas for i in (ctx or [])}
    cur.execute(f"SELECT id, source, hierarchy FROM {TABLE} WHERE id = any(%s)", (list(todos),))
    for i, src, h in cur.fetchall():
        mm = re.search(r'(?i)art[íi]culo\s+(.+?)\s*$', (h or '').split(' > ')[-1])
        art_ctx[i] = (src, re.sub(r'\W+', ' ', mm.group(1)).strip().lower() if mm else None)
    for origen, resp, ctx in filas:
        ctx = set(ctx or [])
        otros_arts = {}   # número de artículo → leyes en el contexto
        for i in ctx:
            src_i, a_i = art_ctx.get(i, (None, None))
            if a_i: otros_arts.setdefault(a_i, set()).add(src_i)
        for src, lab, art, frag in citas(resp):
            if src is None:
                res.append(dict(origen=origen, ley=None, art=art, clase='sin_ley', frag=frag)); continue
            if src not in fuentes:
                res.append(dict(origen=origen, ley=lab, art=art, clase='ley_fuera', frag=frag)); continue
            k = (src, art.lower())
            if k not in cache:
                g = resolve_gold(cur, TABLE, [[{'source': src, 'article': art}]])[0][0]
                ids = g['ids']
                der = False
                if ids:
                    cur.execute(f"SELECT text FROM {TABLE} WHERE id = any(%s)", (ids,))
                    txt = ' '.join(t for (t,) in cur.fetchall())
                    # Derogado = el artículo entero: su texto EMPIEZA con «Se deroga» / «(Derogado)» (no una fracción).
                    cuerpo = re.sub(r'(?is)^.*?\*\*\s*art[íi]culo[^*]*\*\*', '', txt, count=1).strip(' *_.-–—:()\n')[:40]
                    der = bool(DEROG.match(cuerpo))
                cache[k] = (ids, der)
            ids, der = cache[k]
            if ctx & set(ids):
                clase = 'en_contexto'
            elif otros_arts.get(re.sub(r'\W+', ' ', art).strip().lower(), set()) - {src}:
                clase = 'atribucion_cruzada'
            else:
                clase = 'no_existe' if not ids else 'fuera_de_contexto'
            res.append(dict(origen=origen, ley=lab, art=art, clase=clase, derogado=der, frag=frag))
    return res

def resumen(res, filas):
    c = collections.Counter(r['clase'] for r in res)
    clasif = sum(v for k, v in c.items() if k != 'sin_ley')
    print(f'respuestas: {len(filas)} · citas detectadas: {len(res)} (sin ley identificable: {c["sin_ley"]})')
    for k in ('en_contexto', 'fuera_de_contexto', 'atribucion_cruzada', 'no_existe', 'ley_fuera'):
        print(f'  {k:18} {c[k]:4}  {c[k] / clasif:6.1%}' if clasif else k)
    print('  derogados citados:', sum(r.get('derogado', False) for r in res))
    por_resp = collections.Counter()
    for r in res: por_resp[r['origen']] |= 0
    malas = {r['origen'] for r in res if r['clase'] in ('no_existe', 'fuera_de_contexto', 'atribucion_cruzada')}
    inv = {r['origen'] for r in res if r['clase'] == 'no_existe'}
    print(f'  respuestas con ≥1 cita fuera de contexto o inexistente: {len(malas)}/{len(filas)} · con ≥1 inexistente: {len(inv)}/{len(filas)}')
    print('  leyes de las citas «no_existe»:', collections.Counter(r['ley'] for r in res if r['clase'] == 'no_existe').most_common(8))
    print(f'  respuestas con ≥1 atribución cruzada: {len({r["origen"] for r in res if r["clase"] == "atribucion_cruzada"})}/{len(filas)}')
    print('  leyes de las citas «fuera_de_contexto»:', collections.Counter(r['ley'] for r in res if r['clase'] == 'fuera_de_contexto').most_common(8))

if __name__ == '__main__':
    modo = sys.argv[1]
    with connect() as c, c.cursor() as cur:
        if modo == 'estudio':
            cur.execute("""SELECT t.id, t.respuesta, t.contexto FROM estudio_turnos t JOIN estudio_intentos i ON i.id = t.intento_id
                           WHERE t.respuesta IS NOT NULL AND i.codigo <> all(%s)""", (PRUEBAS,))
            filas = [(f'turno {i}', r, [x.get('id') for x in (ctx or []) if x.get('id')]) for i, r, ctx in cur.fetchall()]
        else:
            from shared.object_store import store as st
            filas = []
            for rid in map(int, sys.argv[2:]):
                cur.execute("SELECT artifact_key FROM bench_runs WHERE id=%s", (rid,))
                art = st.get_json(cur.fetchone()[0])
                for q in art.get('results') or art.get('questions') or []:
                    ids = [ch.get('id') for ch in (q.get('chunks') or q.get('context') or []) if isinstance(ch, dict)]
                    filas.append((f'run {rid} q{q.get("question_id")}', q.get('answer') or '', ids))
        res = clasificar(cur, filas)
    resumen(res, filas)
    random.seed(0)
    muestra = {k: random.sample([r for r in res if r['clase'] == k], min(15, sum(r['clase'] == k for r in res)))
               for k in ('no_existe', 'fuera_de_contexto', 'atribucion_cruzada', 'en_contexto', 'sin_ley')}
    out = f'/tmp/citas_{modo}{"_" + "_".join(sys.argv[2:]) if modo != "estudio" else ""}.json'
    json.dump(dict(citas=res, muestra=muestra), open(out, 'w'), ensure_ascii=False, indent=1)
    print('→', out)
