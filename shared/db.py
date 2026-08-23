"""
shared/db.py — one place every lab gets a Postgres connection.

Design notes (read these, they're part of the tutorial):
  * We use SYNC psycopg3, not the async asyncpg in core/. Tutorials read
    top-to-bottom; async would add noise that has nothing to do with RAG.
  * We connect to the ISOLATED `rag_lab` database as role `rag`, using the
    RAG_DB_* vars in labs/.env — never the main app DB.
  * register_vector() teaches psycopg how to send/receive pgvector's `vector`
    type as a plain Python list / numpy array. Without it, vectors come back
    as strings like "[1,2,3]".
"""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

# labs/.env lives one directory up from shared/
_ENV = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV)


def dsn() -> str:
    """Build the connection string from RAG_DB_* env vars."""
    return (
        f"host={os.environ['RAG_DB_HOST']} "
        f"port={os.environ['RAG_DB_PORT']} "
        f"dbname={os.environ['RAG_DB_NAME']} "
        f"user={os.environ['RAG_DB_USER']} "
        f"password={os.environ['RAG_DB_PASSWORD']}"
    )


def connect() -> psycopg.Connection:
    """
    Open a connection to rag_lab with pgvector types registered.
    Requires the SSH tunnel to be up (see labs/README.md).
    """
    conn = psycopg.connect(dsn())
    register_vector(conn)
    return conn
