"""Reingesta de los códigos de Morelos con el chunker vigente (respalda antes y aborta si ya se aplicó).

    cd apps/rewrite_lab && ../../.venv/bin/python ../../ingestion/reingest_morelos.py          # ensayo (dry-run)
    cd apps/rewrite_lab && ../../.venv/bin/python ../../ingestion/reingest_morelos.py --real   # aplica

Para otra reingesta, cambia BAK (nombre del respaldo): si ya existe, el script no hace nada.
"""
import os, sys
from pathlib import Path
LABS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LABS)); sys.path.insert(0, str(LABS / "apps" / "rewrite_lab"))
from dotenv import load_dotenv; load_dotenv(LABS / "apps" / "rewrite_lab" / ".env")
from shared.db import connect
from shared.tei_client import TEIClient
from ingestion.pipeline import ingest_md
TABLE = os.environ.get("LEGAL_TABLE", "sistema_penal__qwen06__legal")
CLEAN = Path(os.environ.get("CLEAN_MD_DIR", LABS / "ingestion" / "out_clean" / "Sistema Penal Acusatorio"))
DOCS = {"CFAMILIAREM.md": ("derecho_familiar", "general"), "CPROFAMEM.md": ("derecho_familiar", "general"),
        "Código PENALEM.md": ("derecho_penal_mexicano", "general")}
dry = "--real" not in sys.argv
BAK = f"{TABLE}_bak_20261002_morelos_v2"   # estado tras el rechunk (sin título), antes de agregar el nombre de la ley
if not dry:
    # Respaldo (con embeddings) para poder revertir, y nunca con una corrida del benchmark en curso.
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT id FROM bench_runs WHERE status = 'running'")
        if cur.fetchall():
            sys.exit("Hay una corrida del benchmark en curso: espera a que termine.")
        # Protección contra doble ejecución: si el respaldo de ESTA versión ya existe, ya se aplicó.
        cur.execute("SELECT to_regclass(%s)", (BAK,))
        if cur.fetchone()[0] and "--force" not in sys.argv:
            sys.exit(f"Ya se aplicó (existe {BAK}). No hago nada; usa --force solo si de verdad quieres repetirla.")
        cur.execute(f"CREATE TABLE {BAK} AS SELECT * FROM {TABLE} WHERE source = ANY(%s)", (list(DOCS),))
        c.commit()
        cur.execute(f"SELECT source, topic, count(*) FROM {BAK} GROUP BY 1, 2")
        print("respaldo:", cur.fetchall())
    # La caché de gold ids del Rewrite Lab no se invalida sola: se aparta tras reingerir.
    cache = LABS / "apps" / "rewrite_lab" / ".gold_ids_cache.json"
    if cache.exists():
        cache.rename(cache.with_name(cache.name + ".bak-20261002-v2"))
tei = TEIClient()
for src, (topic, jur) in DOCS.items():
    r = ingest_md(CLEAN / src, table=TABLE, tei=tei, connect_fn=connect, clean_dir=CLEAN, save_clean=not dry, dry_run=dry)
    if r.error:
        print(src, "ERROR", r.error); continue
    rep = r.report or {}
    d = rep.get("diagnostics", {})
    print(f"== {src}: {rep.get('strategy')} · {r.n_chunks} chunks · limpieza {rep.get('removed_by_reason')} · diagnóstico {d.get('status')}")
    for c in d.get("checks", []):
        if c["level"] != "ok":
            print("   ", c["level"], c["name"], "—", c["summary"], [e.get("detail") for e in c["examples"][:3]])
    if not dry:
        with connect() as c, c.cursor() as cur:
            cur.execute(f"UPDATE {TABLE} SET topic=%s, jurisdiction=%s WHERE source=%s", (topic, jur, src))
            c.commit()
            print("   topic/jur:", cur.rowcount, "filas →", topic, jur)
