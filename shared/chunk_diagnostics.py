"""
shared/chunk_diagnostics.py — ¿el chunking y el etiquetado de un documento quedaron bien?

No corrige nada: REVISA los chunks ya hechos (los del pipeline al ingerir, o los que están
en la BD) y devuelve avisos legibles para que una persona verifique. Nace de los códigos
de Morelos, donde ~2/3 de los artículos del Código Penal quedaron pegados al anterior
("ARTÍCULO *35" no se reconocía) y nadie se enteró hasta que falló el benchmark.

Reglas (cada una → un `check` con nivel ok / warn / bad):
  estrategia  El texto tiene la densidad de artículos de un código, pero los chunks no son
              artículos (se partió por encabezados o párrafos).
  pegados     Un chunk contiene el INICIO de otro artículo además del suyo: ese artículo no
              tiene chunk propio (se busca con una regla más laxa que la del chunker, para
              atrapar justo lo que el chunker no reconoció).
  etiqueta    El chunk dice "Artículo 34" pero su texto empieza con otro artículo (o con
              ninguno).
  secuencia   Huecos en la numeración (…34, 36…): artículos que no tienen chunk. Se dice si
              aparecen pegados en otro chunk o si no aparecen en ningún lado.
  duplicados  El mismo artículo del cuerpo en más de un chunk.
  repetido    Una línea idéntica en muchos chunks distintos: casi siempre encabezado o pie de
              página que sobrevivió a la limpieza.

Entrada: lista de dicts con `title`, `unit_type`, `part`, `text` (con o sin el prefijo
"Fuente: …\\nSección: …" que se antepone para embeber) y opcionalmente `id`/`hierarchy`.
"""

from __future__ import annotations

import re
from collections import Counter

from shared.legal_chunking import _ARTICLE_LATIN

# Inicio de artículo LAXO (a propósito más permisivo que ARTICLE_RE del chunker): cualquier
# "art…o" al inicio de línea, con o sin asterisco/markup, seguido de un número.
LOOSE_ARTICLE_RE = re.compile(r'(?im)^[ \t#>*_|]*(?:[-•·][ \t]+[ \t#>*_]*)?(?:<u>)?[ \t#>*_]*art[a-záéíóú]{0,7}o[ \t]*\*?[ \t]*(\d+)'
                              r'(?:[ºo°](?![a-záéíóú]))?'                     # ordinal: "1o.-"
                              r'((?:[ \t.\-]+(?:' + _ARTICLE_LATIN + r'|\d+|[a-z])(?![a-záéíóú0-9])'
                              r'|[ \t]+[a-záéíóú]{3,14}(?=[ \t]*\.?[ \t]*\**[ \t]*[-–]))*)')
# Inicio de artículo a MITAD de línea, con forma de encabezado (no de cita en prosa: "del
# artículo 174" no lleva asterisco ni ".-"): "CAPÍTULO II DEL DIVORCIO ARTÍCULO *174.-".
_MIDLINE_START = r'(?:ART[ÍI]CULO|Art[íi]culo)[ \t]*\*?[ \t]*{n}(?![0-9])[ \t]*[ºo°]?[ \t]*\**[ \t]*\.?[ \t]*[-–]'
_PREFIX_RE = re.compile(r'^Fuente:[^\n]*\n(?:Secci[óo]n:[^\n]*\n)?\s*')
_LEGAL_LINE_RE = re.compile(
    r'(?i)^(?:art[íi]?c?u?lo\b|libro\b|t[íi]tulo\b|cap[íi]tulo\b|secci[óo]n\b|fracci[óo]n\b|[ivxlc]+\.\s|'
    r'(?:primer|segund|tercer|cuart|quint|sext|s[ée]ptim|octav|noven|d[ée]cim|[úu]nic)\w*\b|'
    r'(?:se deroga|derogad))')
# Notas de reforma ("Párrafo reformado DOF 03-01-2017"): se repiten a propósito, no son mobiliario.
_REFORM_NOTE_LINE_RE = re.compile(r'(?i)\b(?:reformad|adicionad|derogad|recorrid|reubicad)\w*\s+(?:DOF|P\.?\s?O\.?|POGG)\b')

CODE_MIN_ARTICLES = 10
CODE_MIN_DENSITY = 2.0      # artículos por 1000 palabras (misma regla que document_strategy)
REPEAT_MIN_CHUNKS = 5
MAX_EXAMPLES = 12

LEVEL_ORDER = {'ok': 0, 'warn': 1, 'bad': 2}


def body_of(text: str) -> str:
    """Texto del chunk sin el prefijo "Fuente/Sección" que se le pone para embeber."""
    return _PREFIX_RE.sub('', text or '', count=1)


def _norm_label(num: str, suffix: str = '') -> str:
    suffix = re.sub(r'[\s.\-]+', ' ', suffix or '').strip().upper()
    suffix = re.sub(r'^O\b\s*', '', suffix)          # "148 o" = ordinal con espacio, no sufijo
    suffix = suffix.replace('QUARTER', 'QUÁTER').replace('QUATER', 'QUÁTER')
    return (num.lstrip('0') or '0') + (' ' + suffix if suffix else '')


def _starts(text: str) -> list[str]:
    return [_norm_label(m.group(1), m.group(2)) for m in LOOSE_ARTICLE_RE.finditer(text)]


def _title_label(title: str) -> str | None:
    """'Artículo 148 séptimus' → '148 SÉPTIMUS' (la etiqueta del chunker ya viene limpia)."""
    m = re.match(r'(?i)\s*art[íi]culo\s+(\d+)(?:[ºo°](?![a-záéíóú]))?(.*)$', title or '')
    return _norm_label(m.group(1), m.group(2)) if m else None


def _num(label: str) -> int:
    return int(label.split(' ')[0])


def _words(text: str) -> int:
    return len(re.findall(r'\S+', text))


def _check(cid: str, name: str, level: str, summary: str, examples=None, **extra) -> dict:
    return {'id': cid, 'name': name, 'level': level, 'summary': summary,
            'examples': (examples or [])[:MAX_EXAMPLES], 'n_examples': len(examples or []), **extra}


def _body_sequence(labels: list[str]) -> list[str]:
    """Artículos del CUERPO en orden de lectura: se corta donde la numeración se reinicia
    (los transitorios de cada decreto vuelven a empezar en 1)."""
    out, prev = [], None
    for lab in labels:
        n = _num(lab)
        if prev is not None and n < prev - 20:
            break
        out.append(lab)
        prev = max(prev or n, n)
    return out


def diagnose_chunks(chunks: list[dict]) -> dict:
    """Revisa los chunks de UN documento → {status, checks, stats, flags}.
    `flags` = {índice del chunk: [avisos]} para marcar chunks en la vista de revisión."""
    rows = sorted(chunks, key=lambda c: (c.get('position') or 0, c.get('part') or 1))
    bodies = [body_of(c.get('text', '')) for c in rows]
    flags: dict[int, list[str]] = {}

    def flag(i: int, msg: str) -> None:
        msgs = flags.setdefault(i, [])
        if msg not in msgs:
            msgs.append(msg)

    total_words = sum(_words(b) for b in bodies) or 1
    all_starts = [_starts(b) for b in bodies]
    n_starts = sum(len(s) for s in all_starts)
    density = 1000 * n_starts / total_words
    is_article = [c.get('unit_type') == 'article' for c in rows]
    looks_like_code = n_starts >= CODE_MIN_ARTICLES and density >= CODE_MIN_DENSITY
    checks = []

    # ── estrategia ──
    share = sum(is_article) / len(rows) if rows else 0
    if looks_like_code and share < 0.5:
        checks.append(_check('estrategia', 'Tipo de documento', 'bad',
                             f'Parece una ley/código ({n_starts} inicios de artículo, {density:.1f} por 1000 palabras) '
                             f'pero solo el {share:.0%} de los chunks son artículos: se partió por encabezados o '
                             f'párrafos y las etiquetas no dicen el número de artículo.'))
    else:
        checks.append(_check('estrategia', 'Tipo de documento', 'ok',
                             'Ley/código: un chunk por artículo.' if share >= 0.5 else
                             'Documento de doctrina/prosa: se parte por secciones o párrafos.'))

    if looks_like_code:
        # ── pegados + etiqueta ──
        glued, mislabeled = [], []
        for i, (c, starts) in enumerate(zip(rows, all_starts)):
            own = _title_label(c.get('title', '')) if is_article[i] else None
            first_part = (c.get('part') or 1) == 1
            extra = starts[1:] if (own and first_part and starts) else starts
            if own and first_part:
                if not starts:
                    mislabeled.append({'chunk': i, 'label': c.get('title'), 'detail': 'su texto no empieza con ningún artículo'})
                    flag(i, 'etiqueta: el texto no empieza con un artículo')
                elif starts[0] != own:
                    mislabeled.append({'chunk': i, 'label': c.get('title'), 'detail': f'el texto empieza con el artículo {starts[0]}'})
                    flag(i, f'etiqueta: dice {own} pero empieza con {starts[0]}')
            for s in extra:
                if own and s == own:
                    continue
                if own and abs(_num(s) - _num(own)) > 20:   # cita de otro artículo (p. ej. un decreto que transcribe el texto reformado)
                    continue
                glued.append({'chunk': i, 'label': c.get('title'), 'detail': f'contiene el inicio del artículo {s}', 'article': s})
                flag(i, f'contiene también el artículo {s}')
        checks.append(_check('pegados', 'Artículos sin chunk propio', 'bad' if glued else 'ok',
                             f'{len(glued)} artículo(s) empiezan dentro del chunk de otro artículo: no tienen chunk '
                             f'propio y su etiqueta es la del anterior.' if glued else
                             'Cada artículo empieza en su propio chunk.', glued))
        checks.append(_check('etiqueta', 'Etiqueta vs. texto', 'warn' if mislabeled else 'ok',
                             f'{len(mislabeled)} chunk(s) cuyo número de artículo no coincide con su texto.' if mislabeled
                             else 'Cada chunk empieza con el artículo que dice su etiqueta.', mislabeled))

        # ── secuencia ──
        labels = [_title_label(c.get('title', '')) for c, a, in zip(rows, is_article) if a and (c.get('part') or 1) == 1]
        labels = [x for x in labels if x]
        body = _body_sequence(labels)
        nums = sorted({_num(x) for x in body})
        missing = sorted(set(range(nums[0], nums[-1] + 1)) - set(nums)) if nums else []
        glued_nums = {}
        for g in glued:
            glued_nums.setdefault(_num(g['article']), g['label'])
        def where(n: int) -> str:
            if n in glued_nums:
                return f'pegado dentro de «{glued_nums[n]}»'
            rx = re.compile(_MIDLINE_START.format(n=n))
            for i, b in enumerate(bodies):
                if rx.search(b):
                    flag(i, f'el artículo {n} empieza a mitad de una línea')
                    return f'empieza a mitad de una línea dentro de «{rows[i].get("title")}» (p. ej. pegado a un título de capítulo)'
            return 'no aparece en ningún chunk (¿derogado sin texto, o se perdió en la conversión del PDF?)'
        gaps = [{'article': n, 'detail': where(n)} for n in missing]
        lost = sum(1 for g in gaps if 'no aparece' in g['detail'])
        ratio = len(missing) / max(len(nums) + len(missing), 1)
        level = 'ok' if not missing else ('bad' if ratio > 0.05 or lost else 'warn')
        checks.append(_check('secuencia', 'Numeración completa', level,
                             (f'Faltan {len(missing)} de los artículos {nums[0]}–{nums[-1]} ({ratio:.0%})'
                              + (f'; {lost} no aparecen en ningún chunk' if lost else '') + '.') if missing else
                             (f'Artículos {nums[0]}–{nums[-1]} sin huecos.' if nums else 'Sin artículos numerados.'),
                             gaps, first=nums[0] if nums else None, last=nums[-1] if nums else None))

        # ── duplicados ──
        cnt = Counter(body)
        dups = [{'article': lab, 'detail': f'{n} chunks con la misma etiqueta'} for lab, n in cnt.items() if n > 1]
        checks.append(_check('duplicados', 'Artículos repetidos', 'warn' if dups else 'ok',
                             f'{len(dups)} artículo(s) aparecen en más de un chunk.' if dups else 'Ningún artículo repetido.',
                             dups))

    # ── repetido (encabezado/pie de página residual) ──
    line_chunks: dict[str, set] = {}
    for i, b in enumerate(bodies):
        for ln in set(b.splitlines()):
            key = re.sub(r'\s+', ' ', re.sub(r'[*_#>]', '', ln)).strip()
            if len(key.split()) >= 3 and not _LEGAL_LINE_RE.match(key) and not _REFORM_NOTE_LINE_RE.search(key):
                line_chunks.setdefault(key, set()).add(i)
    min_chunks = max(REPEAT_MIN_CHUNKS, int(0.02 * len(rows)))
    rep = sorted(((k, v) for k, v in line_chunks.items() if len(v) >= min_chunks), key=lambda kv: -len(kv[1]))
    for k, v in rep:
        for i in v:
            flag(i, 'texto repetido (¿encabezado de página?)')
    checks.append(_check('repetido', 'Encabezados/pies de página', 'warn' if rep else 'ok',
                         f'{len(rep)} línea(s) se repiten idénticas en muchos chunks: probablemente encabezado o pie de '
                         f'página que no se limpió. Revisa si es texto legítimo.' if rep else
                         'No hay líneas repetidas sospechosas.',
                         [{'line': k[:200], 'detail': f'en {len(v)} chunks'} for k, v in rep]))

    status = max((c['level'] for c in checks), key=LEVEL_ORDER.get, default='ok')
    article_chunks = sum(is_article)
    return {
        'status': status,
        'checks': checks,
        'stats': {'chunks': len(rows), 'article_chunks': article_chunks, 'article_starts': n_starts,
                  'article_density': round(density, 2), 'looks_like_code': looks_like_code,
                  'words_mean': round(total_words / max(len(rows), 1))},
        'flags': flags,
    }
