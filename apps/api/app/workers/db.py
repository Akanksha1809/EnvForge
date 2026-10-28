"""A fresh, short-lived async engine/session per Celery task invocation.

asyncpg connections are bound to the event loop they were created on, and
each task below runs its own `asyncio.run(...)` (a new loop every time) —
reusing the API's module-level engine/pool across tasks would reuse
connections from a now-closed loop. Trading connection-reuse for
correctness here is the right call given task volume is nowhere near
connection-pool-exhaustion territory.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


@asynccontextmanager
async def task_db_session() -> AsyncGenerator[AsyncSession, None]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            yield session
    finally:
        await engine.dispose()
