"""Smoke tests for Sample App A that don't need a real Postgres/Redis —
full integration behavior is exercised instead by EnvForge actually
deploying this app in a provisioned environment (see
apps/api/tests/integration/test_provisioning_live.py).
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    app.state.pool = MagicMock()
    app.state.pool.acquire.return_value.__aenter__ = AsyncMock(
        return_value=MagicMock(fetchval=AsyncMock(return_value=1))
    )
    app.state.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    app.state.redis = AsyncMock()
    app.state.redis.ping = AsyncMock(return_value=True)
    app.state.redis.incr = AsyncMock(return_value=1)

    return TestClient(app)


def test_health_reports_ok_when_dependencies_are_up(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["dependencies"] == {"postgres": True, "redis": True}


def test_hits_increments_via_redis(client: TestClient) -> None:
    resp = client.get("/api/hits")
    assert resp.status_code == 200
    assert resp.json() == {"hits": 1}
