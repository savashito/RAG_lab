"""Genera la tabla `corpus_remisiones`: cada remisión entre artículos del corpus penal («las penas previstas en el
artículo 220 de este Código»), detectada con apps/rewrite_lab/remisiones.py y resuelta contra la tabla del corpus con una
búsqueda EXACTA por código + número de artículo (no por similitud vectorial).

Se guarda una fila por mención, también las rechazadas (nota de reforma, otra ley, transitorio, encabezado pegado…) y
las que no se pudieron resolver, para poder auditar. Los artículos se identifican por código (`source`) + título
(«Artículo 220»), no por el id del fragmento: los ids cambian en cada reingesta. El id del fragmento se guarda solo como
referencia del momento de generar.

Cada corrida REEMPLAZA las filas de los códigos procesados (en una transacción). Volver a correr tras cada reingesta o
cambio del detector:

    cd apps/rewrite_lab
    ../../.venv/bin/python ../../ingestion/generar_remisiones.py            # ensayo: solo cuenta
    ../../.venv/bin/python ../../ingestion/generar_remisiones.py --real     # escribe la tabla
"""
import argparse
import collections
import os
import re
import subprocess
import sys
from pathlib import Path

LABS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(LABS), str(LABS / "apps" / "rewrite_lab")]
from dotenv import load_dotenv  # noqa: E402

load_dotenv(LABS / "apps" / "rewrite_lab" / ".env")
import remisiones as rm  # noqa: E402
from shared.db import connect  # noqa: E402

TABLE = os.environ.get("LEGAL_TABLE", "sistema_penal__qwen06__legal")
TOPIC = "derecho_penal_mexicano"

SCHEMA = """
CREATE TABLE IF NOT EXISTS corpus_remisiones (
    id serial PRIMARY KEY,
    source text NOT NULL,                -- código de origen (nombre del documento del corpus)
    articulo_origen text NOT NULL,       -- «Artículo 224»
    chunk_id_origen int,                 -- id del fragmento al generar (cambia con cada reingesta: solo referencia)
    texto text NOT NULL,                 -- lo que se detectó, literal: «artículo 220»
    articulo_destino text,               -- «220» (None si es relativa)
    relativa text,                       -- 'anterior', 'anteriores', 'siguiente', 'siguientes' o None
    fraccion text,                       -- «VI» si dice «fracción VI del artículo 127»
    ambito text,                         -- 'mismo' | 'mismo_supuesto' | 'otra_ley'
    ley_destino text,                    -- nombre de la otra ley si ambito = 'otra_ley'
    tipo text,                           -- 'directa' | 'multiple' | 'rango' | 'relativa'
    materia text,                        -- 'pena' | 'calificativa' | 'otra'
    rechazo text,                        -- None si se sigue; si no, el motivo (ver remisiones.py)
    estado text NOT NULL,                -- 'resuelta' | 'no_encontrada' | 'rechazada' | 'relativa_multiple'
    titulo_destino text,                 -- «Artículo 220» si se resolvió (mismo código que el origen)
    chunk_id_destino int,                -- id del fragmento destino al generar (solo referencia)
    detector_version text,               -- commit de git del detector
    generado_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS corpus_remisiones_origen ON corpus_remisiones (source, articulo_origen);
CREATE INDEX IF NOT EXISTS corpus_remisiones_resueltas ON corpus_remisiones (source, articulo_origen) WHERE estado = 'resuelta';
"""


def clave(etiqueta: str) -> str:
    """«Artículo 211 Ter», «211 ter», «2o», «2°» → «211ter», «2», para comparar números de artículo."""
    t = (etiqueta or "").lower().replace("artículo", "").replace("articulo", "")
    t = t.replace("quáter", "quater").replace("°", "o").replace("º", "o")
    t = re.sub(r"[^0-9a-záéíóúñ]", "", t)
    return re.sub(r"^(\d+)o$", r"\1", t)


def version() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(LABS), "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "?"


ap = argparse.ArgumentParser()
ap.add_argument("--real", action="store_true", help="escribe la tabla (sin esto solo cuenta)")
args = ap.parse_args()

with connect() as c, c.cursor() as cur:
    cur.execute(f"SELECT id, source, title, position, text FROM {TABLE} WHERE topic = %s AND title LIKE 'Artículo%%' "
                f"ORDER BY source, position, id", (TOPIC,))
    # Solo códigos y leyes: un libro de doctrina con fragmentos «Artículo …» cita OTRAS leyes, y resolver «artículo 20»
    # dentro del mismo libro no tiene sentido.
    rows = [r for r in cur.fetchall() if re.match(r"(?i)(c[oó]digo|ley)\b", r[1])]

# Índice exacto por código: clave del número → (título, id del primer fragmento); y el orden de los artículos
# (para «el artículo anterior / siguiente»).
indice = collections.defaultdict(dict)
orden = collections.defaultdict(list)
for cid, src, title, pos, _ in rows:
    k = clave(title)
    if k not in indice[src]:
        indice[src][k] = (title, cid)
        orden[src].append(title)

ver = version()
filas, cuenta = [], collections.Counter()
for cid, src, title, pos, txt in rows:
    for r in rm.detectar(txt):
        destino, cid_dest = None, None
        if r["rechazo"]:
            estado = "rechazada"
        elif r["tipo"] == "relativa":
            lista = orden[src]
            i = lista.index(title) if title in lista else -1
            if r["relativa"] in ("anterior", "siguiente") and i >= 0:
                j = i - 1 if r["relativa"] == "anterior" else i + 1
                if 0 <= j < len(lista):
                    destino = lista[j]
                    cid_dest = indice[src][clave(destino)][1]
            estado = "resuelta" if destino else "relativa_multiple" if r["relativa"] in ("anteriores", "siguientes") else "no_encontrada"
        else:
            hit = indice[src].get(clave(r["articulo"]))
            destino, cid_dest = hit if hit else (None, None)
            estado = "resuelta" if destino else "no_encontrada"
        if destino == title:   # remitir a sí mismo no sirve
            estado, destino, cid_dest = "rechazada", None, None
        cuenta[estado] += 1
        filas.append((src, title, cid, r["texto"], r["articulo"], r.get("relativa"), r["fraccion"], r["ambito"], r["ley"],
                      r["tipo"], r["materia"], r["rechazo"], estado, destino, cid_dest, ver))

fuentes = sorted({f[0] for f in filas} | {r[1] for r in rows})
print(f"{len(rows)} fragmentos de artículos en {len(fuentes)} documentos · {len(filas)} menciones · {dict(cuenta)}")
porfuente = collections.Counter((f[0], f[12]) for f in filas)
for s in fuentes:
    res = porfuente[(s, "resuelta")]
    if res or porfuente[(s, "no_encontrada")]:
        print(f"   {s[:60]:60s} resueltas {res:4d} · no encontradas {porfuente[(s, 'no_encontrada')]:3d}")

if args.real:
    with connect() as c, c.cursor() as cur:
        cur.execute(SCHEMA)
        cur.execute("DELETE FROM corpus_remisiones WHERE source = ANY(%s)", (fuentes,))
        cur.executemany(
            "INSERT INTO corpus_remisiones (source, articulo_origen, chunk_id_origen, texto, articulo_destino, relativa, fraccion, "
            "ambito, ley_destino, tipo, materia, rechazo, estado, titulo_destino, chunk_id_destino, detector_version) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", filas)
        c.commit()
        cur.execute("SELECT estado, count(*) FROM corpus_remisiones GROUP BY 1 ORDER BY 2 DESC")
        print("tabla corpus_remisiones:", cur.fetchall())
else:
    print("(ensayo: no se escribió nada; usa --real)")
