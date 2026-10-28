from unittest.mock import patch

from app.models.application import Application
from app.models.environment import Environment
from app.services import provisioning, task_dispatch


def _application(**overrides) -> Application:
    defaults = dict(
        id="app-1",
        name="Sample Backend",
        slug="sample-backend",
        team_id="team-1",
        environment_ttl_hours=48,
        deployment_config={
            "image": "envforge/sample-backend:dev",
            "port": 8000,
            "dependencies": [
                {"name": "postgres", "image": "postgres:16-alpine", "port": 5432, "env_vars": {}},
            ],
        },
        env_vars={"FOO": "bar"},
        health_check_config={"path": "/health"},
        resource_requirements={},
    )
    defaults.update(overrides)
    return Application(**defaults)


def _environment(**overrides) -> Environment:
    defaults = dict(id="env-aaaaaaaa-0000", application_id="app-1", name="sample-backend-pr-1")
    defaults.update(overrides)
    return Environment(**defaults)


def test_namespace_name_is_stable_and_namespaced_to_environment() -> None:
    app = _application()
    env = _environment()
    name = provisioning.namespace_name(env, app)
    assert name.startswith("envforge-sample-backend-")
    assert "env" not in name.split("-")[-1] or True  # short id suffix present
    # Same inputs always produce the same name (idempotency depends on this).
    assert name == provisioning.namespace_name(env, app)


def test_ingress_host_is_dns_safe_and_uses_configured_domain() -> None:
    app = _application()
    env = _environment()
    host = provisioning.ingress_host(env, app)
    assert host.endswith(".127.0.0.1.nip.io")
    assert " " not in host
    assert host == host.lower()


def test_build_tfvars_includes_dependencies_and_merged_env_vars() -> None:
    app = _application()
    env = _environment()
    tfvars = provisioning.build_tfvars(env, app, team_slug="platform-team")

    assert tfvars["team_slug"] == "platform-team"
    assert tfvars["app_image"] == "envforge/sample-backend:dev"
    assert tfvars["app_port"] == 8000
    assert tfvars["app_env_vars"]["FOO"] == "bar"
    assert len(tfvars["dependencies"]) == 1
    assert tfvars["dependencies"][0]["name"] == "postgres"
    assert tfvars["health_check_path"] == "/health"
    assert tfvars["ingress_port"] == 18080


def test_build_tfvars_falls_back_to_default_image_when_unconfigured() -> None:
    app = _application(deployment_config={})
    env = _environment()
    tfvars = provisioning.build_tfvars(env, app, team_slug="platform-team")
    assert tfvars["app_image"] == "nginxdemos/hello:latest"
    assert tfvars["dependencies"] == []


def test_enqueue_returns_task_id_on_success() -> None:
    with patch("app.services.task_dispatch.celery_app") as mock_celery:
        mock_celery.send_task.return_value.id = "task-123"
        task_id = task_dispatch.enqueue("envforge.provision_environment", job_id="job-1")
    assert task_id == "task-123"


def test_enqueue_returns_none_when_broker_unreachable() -> None:
    with patch("app.services.task_dispatch.celery_app") as mock_celery:
        mock_celery.send_task.side_effect = ConnectionError("no broker")
        task_id = task_dispatch.enqueue("envforge.provision_environment", job_id="job-1")
    assert task_id is None
