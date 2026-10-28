"""Test fixtures.

Unit/integration tests run against an in-memory SQLite database (fast, zero
setup) rather than Postgres — the ORM layer doesn't use any Postgres-specific
types, so this is a faithful stand-in and keeps `pytest` runnable with no
external services. True Postgres-dependent behavior (if any is ever added)
would get a separate `@pytest.mark.postgres` suite run against the compose
`postgres` service in CI.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (populate Base.metadata)
from app.db.base import Base
from app.db.session import get_db


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    from app.main import app

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def register_and_login(
    client: AsyncClient,
    email: str,
    *,
    full_name: str = "Test User",
    password: str = "supersecret123",
) -> dict[str, str]:
    """Shared helper for integration tests: registers a user (the first one
    in a given test's DB becomes platform_admin — see auth_service) and
    returns Authorization headers for it."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": full_name, "password": password},
    )
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
