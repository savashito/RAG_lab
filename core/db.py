import asyncpg
from core.config import settings

_pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    """Create the connection pool. Called once at app startup."""
    global _pool
    _pool = await asyncpg.create_pool(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        min_size=2,
        max_size=10,
    )


async def close_pool() -> None:
    """Gracefully close the pool. Called at app shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """
    Return the active pool.
    Plain def — no I/O, just returns the already-created pool.
    Raises RuntimeError if called before init_pool().
    """
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_pool() at startup")
    return _pool
