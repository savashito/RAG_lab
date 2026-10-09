"""Qué código o ley del corpus menciona un texto («Ciudad de México» → Código Penal de la CDMX).

Lo usan el routing por código de la búsqueda (además de la búsqueda normal, busca dentro de
cada código mencionado) y el benchmark (a qué ley pertenece cada artículo de un must).

La detección no usa LLM: compara el texto con alias de cada código tras normalizar acentos,
mayúsculas y signos ("Querétaro" = "queretaro"), y tolera una errata (una letra de más, de menos
o cambiada) en palabras largas ("Queretro", "Distito Federal"). Las siglas (CDMX, CPF, CNPP…)
deben coincidir exactas: con tolerancia, siglas cortas chocarían entre sí.

Para una ley nueva: agregar una entrada a CODE_ROUTES. El alias debe nombrar la LEY, no el
delito: "materia de secuestro" (parte del nombre de la ley), no "secuestro" a secas.
"""
from __future__ import annotations

import re
import unicodedata

# (etiqueta corta, documento del corpus, alias en palabras, siglas exactas).
# Si dos alias se traslapan en el texto gana el más largo ("Código Procesal Familiar" no
# cuenta además como "Código Familiar").
CODE_ROUTES = [
    ('CNPCF', 'Código Nacional de Procedimientos Civiles y Familiares.md',
     ['procedimientos civiles y familiares'], ['cnpcf']),
    ('CPFM', 'CPROFAMEM.md', ['codigo procesal familiar'], ['cprofamem']),
    ('CFM', 'CFAMILIAREM.md', ['codigo familiar'], ['cfamiliarem']),
    ('CDMX', 'Código Penal de la Ciudad de México.md',
     ['ciudad de mexico', 'distrito federal', 'd f'], ['cdmx', 'cpcdmx', 'cpdf', 'df']),
    ('CPEM', 'Código Penal del Estado de México.md', ['estado de mexico'], ['cpem', 'edomex']),
    ('CPF', 'Código Penal Federal.md', ['codigo penal federal'], ['cpf']),
    ('CNPP', 'Código Nacional de Procedimientos Penales.md', ['procedimientos penales'], ['cnpp']),
    ('Morelos', 'Código PENALEM.md', ['morelos'], ['penalem']),
    ('Querétaro', 'Código Penal del Estado de Querétaro.md', ['queretaro'], ['qro']),
    ('LGSecuestro', 'Ley General para Delitos en Materia de Secuestro.md',
     ['materia de secuestro', 'ley general de secuestro', 'ley antisecuestro'], ['lgpsdms']),
    ('LGExtorsión', 'Ley General para Prevenir, Investigar y Sancionar Delitos en Materia de Extorsión.md',
     ['materia de extorsion', 'ley general de extorsion'], []),
    ('LFCDO', 'Ley Federal Contra la Delincuencia Organizada.md',
     ['ley federal contra la delincuencia organizada', 'ley contra la delincuencia organizada'], ['lfcdo']),
    ('LGV', 'Ley General de Víctimas.md', ['ley general de victimas'], []),
]

# Una errata solo se tolera en palabras de al menos estas letras: en un alias de varias palabras
# el resto de la frase da contexto; uno de una sola palabra necesita más ("morelos" ≈ "modelos").
FUZZY_MIN_IN_PHRASE = 6
FUZZY_MIN_SINGLE = 8


def fold(text: str) -> str:
    """Minúsculas, sin acentos, signos → espacio."""
    t = unicodedata.normalize('NFD', text or '')
    t = ''.join(ch for ch in t if unicodedata.category(ch) != 'Mn').lower()
    return re.sub(r'[^a-z0-9ñ]+', ' ', t).strip()


def _words(text: str) -> list[tuple[str, int]]:
    """Palabras normalizadas con su posición (en caracteres) en el texto ORIGINAL."""
    out = []
    for m in re.finditer(r'[^\W_]+', text or ''):
        w = fold(m.group(0))
        if w:
            out.append((w, m.start()))
    return out


def _within_one(a: str, b: str) -> bool:
    """¿Distancia de edición ≤ 1 (insertar, borrar o cambiar una letra)?"""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la > lb:
        a, b, la, lb = b, a, lb, la
    i = 0
    while i < la and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:] if la < lb else a[i + 1:] == b[i + 1:]


def _word_match(word: str, alias_word: str, min_len: int) -> bool:
    return word == alias_word or (len(alias_word) >= min_len and _within_one(word, alias_word))


def codes_in(text: str) -> list[dict]:
    """Códigos mencionados en `text`, en orden de aparición y sin repetir:
    [{'label', 'source', 'start', 'match'}]."""
    words = _words(text)
    hits = []   # (start_word, end_word, route)
    for route in CODE_ROUTES:
        label, source, aliases, acronyms = route
        for alias in aliases:
            aw = alias.split()
            min_len = FUZZY_MIN_SINGLE if len(aw) == 1 else FUZZY_MIN_IN_PHRASE
            for i in range(len(words) - len(aw) + 1):
                if all(_word_match(words[i + j][0], aw[j], min_len) for j in range(len(aw))):
                    hits.append((i, i + len(aw), route))
        for acr in acronyms:
            hits.extend((i, i + 1, route) for i, (w, _) in enumerate(words) if w == acr)
    # Traslapes: gana el alias más largo; luego, el primero.
    hits.sort(key=lambda h: (-(h[1] - h[0]), h[0]))
    taken, kept = set(), []
    for s, e, route in hits:
        if taken.isdisjoint(range(s, e)):
            taken.update(range(s, e))
            kept.append((s, e, route))
    out, seen = [], set()
    for s, e, (label, source, _, _) in sorted(kept, key=lambda h: h[0]):
        if source not in seen:
            seen.add(source)
            start = words[s][1]
            end_word = words[e - 1]
            out.append({'label': label, 'source': source, 'start': start,
                        'match': (text or '')[start:end_word[1] + len(end_word[0])]})
    return out


def short_label(source: str | None) -> str:
    return next((label for label, src, _, _ in CODE_ROUTES if src == source), '?')
