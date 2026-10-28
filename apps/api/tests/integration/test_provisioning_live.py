"""Exercises the real Terraform/kubectl provisioning pipeline against a
live local `kind` cluster — not mocked. Skipped automatically when no such
cluster is reachable (e.g. in CI, which has no kind cluster). Run locally
with `make kind-up && make kind-ingress && make build-sample-backend`
first, then `pytest -m requires_kind`.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.models.application import Application
from app.models.environment import Environment
from app.services import provisioning

REPO_ROOT = Path(__file__).resolve().parents[4]
TF_MODULE_ROOT = REPO_ROOT / "infrastructure" / "terraform" / "environments" / "local"

pytestmark = pytest.mark.requires_kind


def _kind_cluster_available() -> bool:
    if shutil.which("kubectl") is None or shutil.which("terraform") is None:
        return False
    try:
        result = subprocess.run(
            ["kubectl", "--context=kind-envforge", "get", "nodes"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


@pytest.mark.skipif(
    not _kind_cluster_available(), reason="no live kind-envforge cluster / terraform / kubectl"
)
def test_apply_and_destroy_environment_against_real_kind_cluster(monkeypatch) -> None:
    monkeypatch.setenv("TERRAFORM_MODULE_ROOT", str(TF_MODULE_ROOT))
    get_settings.cache_clear()

    application = Application(
        id="app-live-0001",
        name="Live Smoke",
        slug="live-smoke",
        team_id="team-live-0001",
        deployment_config={
            "image": "envforge/sample-backend:dev",
            "port": 8000,
            "dependencies": [
                {
                    "name": "postgres",
                    "image": "postgres:16-alpine",
                    "port": 5432,
                    "env_vars": {"POSTGRES_PASSWORD": "postgres", "POSTGRES_DB": "postgres"},
                },
                {"name": "redis", "image": "redis:7-alpine", "port": 6379, "env_vars": {}},
            ],
        },
        env_vars={
            "DATABASE_URL": "postgresql://postgres:postgres@postgres:5432/postgres",
            "REDIS_URL": "redis://redis:6379/0",
        },
        health_check_config={"path": "/health"},
    )
    environment = Environment(
        id="env-live-0001", application_id=application.id, name="live-smoke-manual"
    )

    try:
        outputs = provisioning.apply_environment(environment, application, team_slug="platform")
        assert outputs["namespace_name"]
        assert outputs["preview_url"]

        healthy = provisioning.wait_for_health(
            application, outputs["namespace_name"], timeout_seconds=120
        )
        assert healthy, "sample-backend pod did not become Ready in time"
    finally:
        provisioning.destroy_environment(environment)
        get_settings.cache_clear()
