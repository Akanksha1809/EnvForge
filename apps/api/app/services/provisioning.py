"""Real infrastructure provisioning via Terraform + kubectl against the
local `kind` cluster (see infrastructure/terraform/environments/local and
docs/architecture.md for why local kind rather than a mocked provisioner).

Each environment gets its own Terraform workspace directory with its own
local state file — `environment_id` is the stable key, so re-running apply
for the same environment is idempotent (Terraform reconciles against its
existing state rather than creating duplicate resources).
"""

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.application import Application
from app.models.environment import Environment

logger = get_logger("envforge.provisioning")


class ProvisioningError(Exception):
    def __init__(self, message: str, *, stdout: str = "", stderr: str = "") -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr


_SLUG_RE = re.compile(r"[^a-z0-9-]")


def _slugify(value: str) -> str:
    return _SLUG_RE.sub("-", value.lower()).strip("-")[:48]


def namespace_name(environment: Environment, application: Application) -> str:
    settings = get_settings()
    short_id = environment.id.split("-")[0]
    return f"{settings.provisioning_namespace_prefix}-{_slugify(application.slug)}-{short_id}"


def ingress_host(environment: Environment, application: Application) -> str:
    settings = get_settings()
    short_id = environment.id.split("-")[0]
    return f"{_slugify(application.slug)}-{short_id}.{settings.ingress_base_domain}"


def build_tfvars(
    environment: Environment, application: Application, team_slug: str
) -> dict[str, Any]:
    """Translate an Environment + its Application's config into the
    variables the Terraform root module expects. Template-driven resource
    limits / required services (basic-backend vs fullstack vs
    microservices) are honored once Application.deployment_config carries
    them; until then this falls back to the module's own defaults."""
    settings = get_settings()
    deployment_config = application.deployment_config or {}

    dependencies = [
        {
            "name": dep["name"],
            "image": dep["image"],
            "port": dep["port"],
            "env_vars": dep.get("env_vars", {}),
        }
        for dep in deployment_config.get("dependencies", [])
    ]

    tfvars: dict[str, Any] = {
        "kube_context": settings.kube_context,
        # The *effective* (possibly host.docker.internal-rewritten) path —
        # the kubernetes provider reads `config_path` directly from this
        # tfvar, so setting KUBECONFIG in the subprocess environment alone
        # has no effect on it.
        "kubeconfig_path": _effective_kubeconfig_path(settings.kubeconfig_path),
        "environment_id": environment.id,
        "namespace_name": namespace_name(environment, application),
        "application_slug": application.slug,
        "team_slug": team_slug,
        "app_name": _slugify(application.slug),
        "app_image": deployment_config.get("image", "nginxdemos/hello:latest"),
        "app_port": deployment_config.get("port", 8000),
        "app_replicas": deployment_config.get("replicas", 1),
        "app_env_vars": {**application.env_vars, **deployment_config.get("env_vars", {})},
        "app_secret_env_vars": deployment_config.get("secret_env_vars", {}),
        "health_check_path": (application.health_check_config or {}).get("path", "/health"),
        "ingress_host": ingress_host(environment, application),
        "ingress_port": settings.ingress_host_port,
        "dependencies": dependencies,
    }
    if application.resource_requirements:
        tfvars["app_resources"] = application.resource_requirements
    return tfvars


def _effective_kubeconfig_path(configured_path: str) -> str:
    """Inside the worker container, the host's kubeconfig points at
    `https://127.0.0.1:<port>`, which inside the container is the
    container itself, not the Docker host running `kind`. Rewrite the
    cluster server address to `host.docker.internal` (see the worker's
    `extra_hosts` entry in docker-compose.yml) and write a patched copy
    for Terraform to use instead."""
    settings = get_settings()
    if not settings.running_in_docker:
        return configured_path

    source = Path(configured_path).expanduser()
    with source.open() as f:
        config = yaml.safe_load(f)

    for cluster in config.get("clusters", []):
        server = cluster.get("cluster", {}).get("server", "")
        patched, rewritten = re.subn(
            r"https://(127\.0\.0\.1|localhost|0\.0\.0\.0)(:\d+)",
            r"https://host.docker.internal\2",
            server,
        )
        cluster["cluster"]["server"] = patched
        if rewritten:
            # kind's API server certificate has no `host.docker.internal`
            # SAN (it's only ever issued for 127.0.0.1/localhost/the
            # cluster's own hostnames), so verifying it against that name
            # always fails even though the connection is genuinely the
            # same local cluster. Skipping verification here is safe
            # specifically because this path only ever targets a local
            # `kind` cluster reached through the Docker host gateway —
            # never a real/cloud target, which always keeps its own
            # kubeconfig untouched.
            cluster["cluster"].pop("certificate-authority-data", None)
            cluster["cluster"]["insecure-skip-tls-verify"] = True

    patched_path = Path("/tmp/envforge/kubeconfig-docker.yaml")
    patched_path.parent.mkdir(parents=True, exist_ok=True)
    with patched_path.open("w") as f:
        yaml.safe_dump(config, f)
    return str(patched_path)


def workspace_dir(environment_id: str) -> Path:
    """Where this environment's root module (and its state) lives. Nested
    under environments/local to mirror the source tree's layout — the root
    module's `../../modules/...` source paths only resolve correctly if
    that relative structure is preserved in the copy (see
    `_prepare_workspace`), not flattened into a single directory."""
    settings = get_settings()
    return Path(settings.terraform_workspace_root) / environment_id / "environments" / "local"


def _prepare_workspace(environment_id: str) -> Path:
    settings = get_settings()
    module_root = Path(settings.terraform_module_root)
    modules_source = module_root.parent.parent / "modules"

    target_env = workspace_dir(environment_id)
    target_env.mkdir(parents=True, exist_ok=True)
    target_modules = target_env.parent.parent / "modules"
    if not target_modules.exists():
        shutil.copytree(modules_source, target_modules)

    for tf_file in module_root.glob("*.tf"):
        shutil.copy2(tf_file, target_env / tf_file.name)

    return target_env


def _run(
    args: list[str], *, cwd: Path, env_overrides: dict[str, str], timeout: int = 600
) -> subprocess.CompletedProcess[str]:
    import os

    settings = get_settings()
    env = {**os.environ, **env_overrides}
    full_args = [settings.terraform_binary, *args]
    logger.info("terraform.run", args=full_args, cwd=str(cwd))
    result = subprocess.run(
        full_args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        logger.error("terraform.failed", args=full_args, stderr=result.stderr[-4000:])
        raise ProvisioningError(
            f"`{' '.join(full_args)}` failed with exit code {result.returncode}",
            stdout=result.stdout,
            stderr=result.stderr,
        )
    return result


def apply_environment(
    environment: Environment, application: Application, team_slug: str
) -> dict[str, Any]:
    """Runs `terraform init` + `apply` for this environment's workspace
    against the real local kind cluster and returns the parsed outputs
    (namespace_name, preview_url, service_name). Raises ProvisioningError
    on any failure — callers are responsible for the FAILED transition."""
    settings = get_settings()
    tf_dir = _prepare_workspace(environment.id)
    tfvars = build_tfvars(environment, application, team_slug)
    (tf_dir / "terraform.tfvars.json").write_text(json.dumps(tfvars, indent=2))

    kubeconfig = _effective_kubeconfig_path(settings.kubeconfig_path)
    env_overrides = {"KUBECONFIG": str(Path(kubeconfig).expanduser())}

    _run(["init", "-input=false"], cwd=tf_dir, env_overrides=env_overrides)
    _run(
        ["apply", "-auto-approve", "-input=false"],
        cwd=tf_dir,
        env_overrides=env_overrides,
        timeout=600,
    )
    output_result = _run(["output", "-json"], cwd=tf_dir, env_overrides=env_overrides, timeout=60)
    raw_outputs = json.loads(output_result.stdout)
    return {key: value["value"] for key, value in raw_outputs.items()}


def _pod_is_ready(pod: dict[str, Any]) -> bool:
    for condition in pod.get("status", {}).get("conditions", []):
        if condition.get("type") == "Ready":
            return condition.get("status") == "True"
    return False


def wait_for_health(
    application: Application, namespace: str, *, timeout_seconds: int = 120
) -> bool:
    """Polls the Kubernetes API (not the app's HTTP endpoint directly —
    see docs/architecture.md on why) for the app's Pod `Ready` condition,
    which kubelet only sets once the container's own readiness probe (the
    app's `/health` endpoint, wired up in the environment-app Terraform
    module) has passed. This is the real health check the spec asks for;
    it just goes through the K8s control plane instead of an app-level
    HTTP call, which also works regardless of whether the caller (this
    worker) can reach the cluster's ingress."""
    settings = get_settings()
    kubeconfig = _effective_kubeconfig_path(settings.kubeconfig_path)
    app_name = _slugify(application.slug)
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                "kubectl",
                f"--kubeconfig={Path(kubeconfig).expanduser()}",
                f"--context={settings.kube_context}",
                "-n",
                namespace,
                "get",
                "pods",
                "-l",
                f"app={app_name}",
                "-o",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            pods = json.loads(result.stdout).get("items", [])
            if pods and all(_pod_is_ready(pod) for pod in pods):
                return True
        time.sleep(3)

    return False


def destroy_environment(environment: Environment) -> None:
    """Runs `terraform destroy` for this environment's workspace. A
    missing workspace (e.g. the environment never got past QUEUED) is a
    no-op, not an error."""
    settings = get_settings()
    tf_dir = workspace_dir(environment.id)
    if not tf_dir.exists() or not (tf_dir / "terraform.tfstate").exists():
        logger.info("terraform.destroy.skipped_no_state", environment_id=environment.id)
        return

    kubeconfig = _effective_kubeconfig_path(settings.kubeconfig_path)
    env_overrides = {"KUBECONFIG": str(Path(kubeconfig).expanduser())}
    _run(
        ["destroy", "-auto-approve", "-input=false"],
        cwd=tf_dir,
        env_overrides=env_overrides,
        timeout=300,
    )
    # tf_dir is .../<environment_id>/environments/local — remove the whole
    # per-environment workspace (including the copied modules/ tree), not
    # just the leaf directory.
    shutil.rmtree(tf_dir.parent.parent, ignore_errors=True)


def list_managed_namespaces() -> list[dict[str, str]]:
    """Every real namespace in the cluster EnvForge created, by label
    (see infrastructure/terraform/modules/environment-namespace) — the
    source of truth the orphan-detection sweep (Phase 5) cross-references
    against the Environment table, since a namespace with no matching
    non-terminal Environment row is, by definition, orphaned."""
    settings = get_settings()
    kubeconfig = _effective_kubeconfig_path(settings.kubeconfig_path)
    result = subprocess.run(
        [
            "kubectl",
            f"--kubeconfig={Path(kubeconfig).expanduser()}",
            f"--context={settings.kube_context}",
            "get",
            "namespaces",
            "-l",
            "envforge.io/managed=true",
            "-o",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        logger.warning("provisioning.list_namespaces_failed", stderr=result.stderr[-2000:])
        return []

    namespaces = json.loads(result.stdout).get("items", [])
    return [
        {
            "name": ns["metadata"]["name"],
            "environment_id": ns["metadata"].get("labels", {}).get("envforge.io/environment", ""),
        }
        for ns in namespaces
    ]


def delete_namespace_directly(namespace: str) -> None:
    """Fallback for a true orphan with no corresponding Environment row
    (so there's no Terraform workspace/state to run `destroy` against) —
    deletes the Kubernetes namespace directly. Real environments are
    always torn down via `destroy_environment` instead, which goes
    through Terraform."""
    settings = get_settings()
    kubeconfig = _effective_kubeconfig_path(settings.kubeconfig_path)
    result = subprocess.run(
        [
            "kubectl",
            f"--kubeconfig={Path(kubeconfig).expanduser()}",
            f"--context={settings.kube_context}",
            "delete",
            "namespace",
            namespace,
            "--wait=false",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise ProvisioningError(
            f"Failed to delete orphaned namespace '{namespace}'", stderr=result.stderr
        )
