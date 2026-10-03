"""Reingesta de documentos ya ingeridos con el chunker vigente, a partir de su Markdown limpio.

Conserva el `topic` y la `jurisdiction` que cada documento tiene HOY en la tabla, respalda sus
chunks (con embeddings) antes de reemplazarlos y se niega a correr dos veces con el mismo
respaldo (protección contra doble ejecución; --force para repetir a propósito).

    cd apps/rewrite_lab
    ../../.venv/bin/python ../../ingestion/reingest_docs.py --backup <sufijo> "Doc 1.md" "Doc 2.md"          # ensayo
    ../../.venv/bin/python ../../ingestion/reingest_docs.py --backup <sufijo> --real "Doc 1.md" "Doc 2.md"   # aplica

Revertir: DELETE de esos sources en la tabla + INSERT … SELECT * FROM <tabla>_bak_<sufijo>, y
reiniciar la app (el índice BM25 vive en memoria).
"""
import argparse
import os
import sys
from pathlib import Path

LABS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LABS)); sys.path.insert(0, str(LABS / "apps" / "rewrite_lab"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(LABS / "apps" / "rewrite_lab" / ".env")
from ingestion.pipeline import ingest_md  # noqa: E402
from shared.db import connect  # noqa: E402
from shared.tei_client import TEIClient  # noqa: E402

TABLE = os.environ.get("LEGAL_TABLE", "sistema_penal__qwen06__legal")
CLEAN = Path(os.environ.get("CLEAN_MD_DIR", LABS / "ingestion" / "out_clean" / "Sistema Penal Acusatorio"))

ap = argparse.ArgumentParser()
ap.add_argument("sources", nargs="+")
ap.add_argument("--backup", required=True, help="sufijo del respaldo: <tabla>_bak_<sufijo>")
ap.add_argument("--real", action="store_true")
ap.add_argument("--force", action="store_true")
args = ap.parse_args()
BAK = f"{TABLE}_bak_{args.backup}"

with connect() as c, c.cursor() as cur:
    cur.execute(f"SELECT source, max(topic), max(jurisdiction), count(*) FROM {TABLE} WHERE source = ANY(%s) GROUP BY 1",
                (args.sources,))
    meta = {s: (t, j, n) for s, t, j, n in cur.fetchall()}
missing = [s for s in args.sources if s not in meta or not (CLEAN / s).is_file()]
if missing:
    sys.exit(f"Sin chunks en la tabla o sin Markdown limpio: {missing}")

if args.real:
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT id FROM bench_runs WHERE status = 'running'")
        if cur.fetchall():
            sys.exit("Hay una corrida del benchmark en curso: espera a que termine.")
        cur.execute("SELECT to_regclass(%s)", (BAK,))
        if cur.fetchone()[0] and not args.force:
            sys.exit(f"Ya se aplicó (existe {BAK}). No hago nada; usa --force solo si de verdad quieres repetirla.")
        cur.execute(f"CREATE TABLE {BAK} AS SELECT * FROM {TABLE} WHERE source = ANY(%s)", (args.sources,))
        c.commit()
        cur.execute(f"SELECT source, count(*) FROM {BAK} GROUP BY 1")
        print("respaldo:", cur.fetchall())
    # La caché de gold ids del Rewrite Lab no se invalida sola: se aparta tras reingerir.
    cache = LABS / "apps" / "rewrite_lab" / ".gold_ids_cache.json"
    if cache.exists():
        cache.rename(cache.with_name(f"{cache.name}.bak-{args.backup}"))

tei = TEIClient()
for src in args.sources:
    topic, jur, before = meta[src]
    r = ingest_md(CLEAN / src, table=TABLE, tei=tei, connect_fn=connect, clean_dir=CLEAN,
                  save_clean=args.real, dry_run=not args.real)
    if r.error:
        print(src, "ERROR", r.error)
        continue
    rep = r.report or {}
    d = rep.get("diagnostics", {})
    print(f"== {src}: {before} → {r.n_chunks} chunks · {rep.get('strategy')} · limpieza {rep.get('removed_by_reason')} · "
          f"diagnóstico {d.get('status')}")
    for chk in d.get("checks", []):
        if chk["level"] != "ok":
            print("   ", chk["level"], chk["name"], "—", chk["summary"])
    if args.real:
        with connect() as c, c.cursor() as cur:
            cur.execute(f"UPDATE {TABLE} SET topic = %s, jurisdiction = %s WHERE source = %s", (topic, jur, src))
            c.commit()
            print(f"   topic/jur: {cur.rowcount} filas → {topic} · {jur}")
