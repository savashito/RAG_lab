"""Separa cada documento de out_clean con el separador viejo y con el nuevo y compara los fragmentos. Solo lectura."""
import importlib.util, sys, collections
from pathlib import Path
sys.path.insert(0, '/home/tlacua/apps/RAG_lab')
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
old = load('lc_old', '/tmp/chunkcmp/legal_chunking_old.py')
new = load('lc_new', '/tmp/chunkcmp/legal_chunking.py')
docs = sorted(Path('/home/tlacua/apps/RAG_lab/ingestion/out_clean').rglob('*.md'))
total_old = total_new = 0; distintos = 0
for p in docs:
    text = p.read_text(encoding='utf-8', errors='replace')
    so, sn = old.document_strategy(text), new.document_strategy(text)
    try:
        co = old.chunk_documents({p.name: text})
    except Exception as e:  # noqa: BLE001
        co = None; eo = type(e).__name__
    try:
        cn = new.chunk_documents({p.name: text})
    except Exception as e:  # noqa: BLE001
        cn = None; en = type(e).__name__
    if co is None or cn is None:
        print(f'! {p.name}: no se pudo separar (viejo: {"ok" if co is not None else eo}, nuevo: {"ok" if cn is not None else en}) · {len(text)} caracteres')
        continue
    total_old += len(co); total_new += len(cn)
    key = lambda df: collections.Counter(zip(df['hierarchy'].fillna(''), df['text_for_embedding'])) if len(df) else collections.Counter()
    ko, kn = key(co), key(cn)
    if so != sn or ko != kn:
        distintos += 1
        solo_old = [h.split(' > ')[-1] for (h, t), n in (ko - kn).items()]
        solo_new = [h.split(' > ')[-1] for (h, t), n in (kn - ko).items()]
        print(f'≠ {p.relative_to(p.parents[1])}: estrategia {so}→{sn} · fragmentos {len(co)}→{len(cn)}')
        print('    solo en el viejo:', solo_old[:12])
        print('    solo en el nuevo:', solo_new[:12])
print(f'\n{len(docs)} documentos · {distintos} con diferencias · fragmentos {total_old} → {total_new}')
