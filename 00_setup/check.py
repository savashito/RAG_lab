"""
Lab 00 — Setup & sanity check.

Goal: prove the whole chain works BEFORE we build anything on top of it:
  laptop  ->  SSH tunnel (:5433)  ->  rag_lab  ->  pgvector

It does three things:
  1. Connects to rag_lab.
  2. Confirms the pgvector extension is present.
  3. Does a real vector round-trip: creates a tiny table, inserts 3 vectors,
     and asks Postgres for the nearest neighbour to a query vector using the
     cosine-distance operator `<=>`. This is the ONE operation every vector
     database is built around — here you see it naked, in plain SQL.

Run (with the tunnel open in another terminal):
    uv run python 00_setup/check.py
"""

import sys

import numpy as np

# make `shared` importable when run from the labs/ root
sys.path.insert(0, ".")
from shared.db import connect


def main() -> None:
    with connect() as conn, conn.cursor() as cur:
        # 1. Who/where are we?
        cur.execute("SELECT current_database(), current_user, version()")
        db, user, version = cur.fetchone()
        print(f"✓ connected to '{db}' as '{user}'")
        print(f"  {version.split(' on ')[0]}")

        # 2. Is pgvector here?
        cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        row = cur.fetchone()
        if not row:
            print("✗ pgvector NOT installed in this database")
            sys.exit(1)
        print(f"✓ pgvector {row[0]}")

        # 3. Vector round-trip -------------------------------------------------
        # A throwaway table with a 3-dimensional vector column.
        cur.execute("DROP TABLE IF EXISTS _lab00_smoke")
        cur.execute("CREATE TABLE _lab00_smoke (id int, name text, embedding vector(3))")

        rows = [
            (1, "apple",  np.array([1.0, 0.0, 0.0])),
            (2, "banana", np.array([0.9, 0.1, 0.0])),
            (3, "rocket", np.array([0.0, 0.0, 1.0])),
        ]
        cur.executemany(
            "INSERT INTO _lab00_smoke (id, name, embedding) VALUES (%s, %s, %s)", rows
        )

        # Query: what is closest to "apple-ish" [1,0,0]?
        # `<=>` is COSINE DISTANCE (0 = identical direction, 2 = opposite).
        query = np.array([1.0, 0.0, 0.0])
        cur.execute(
            """
            SELECT name, embedding <=> %s AS cosine_distance
            FROM _lab00_smoke
            ORDER BY cosine_distance
            LIMIT 3
            """,
            (query,),
        )
        print("\n  nearest neighbours to [1,0,0] (cosine distance):")
        for name, dist in cur.fetchall():
            print(f"    {name:<8} {dist:.4f}")

        cur.execute("DROP TABLE _lab00_smoke")
        conn.commit()

    print("\n✓ Lab 00 passed — infrastructure is ready.")


if __name__ == "__main__":
    main()
