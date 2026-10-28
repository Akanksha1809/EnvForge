"""Central application configuration, loaded from environment variables.

All environment-specific values live here (12-factor style) — nothing in the
rest of the codebase should read `os.environ` directly.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # General
    app_name: str = "EnvForge"
    environment: Literal["local", "ci", "staging", "production"] = "local"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"

    # Database
    database_url: str = "postgresql+asyncpg://envforge:envforge@localhost:5432/envforge"
    database_echo: bool = False

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Auth / security
    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION_envforge_dev_secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 7

    # GitHub OAuth (optional — platform runs fine without these via local auth)
    github_oauth_client_id: str | None = None
    github_oauth_client_secret: str | None = None
    github_oauth_redirect_uri: str = "http://localhost:5173/auth/github/callback"

    # GitHub App / webhook integration (for PR automation, independent of OAuth login)
    github_webhook_secret: str = "CHANGE_ME_dev_webhook_secret"
    github_api_token: str | None = None
    github_api_base_url: str = "https://api.github.com"

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # Provisioning
    terraform_binary: str = "terraform"
    terraform_module_root: str = "/infrastructure/terraform/environments/local"
    terraform_workspace_root: str = "/tmp/envforge/terraform-workspaces"
    kubeconfig_path: str = "~/.kube/config"
    kube_context: str = "kind-envforge"
    provisioning_namespace_prefix: str = "envforge"
    default_environment_ttl_hours: int = 48
    max_concurrent_provisioning_jobs: int = 5
    ingress_base_domain: str = "127.0.0.1.nip.io"
    ingress_host_port: int = 18080
    # True inside the worker container: Terraform there needs to reach the
    # kind cluster's API server through the Docker host rather than via the
    # 127.0.0.1 address the host's own kubeconfig records.
    running_in_docker: bool = False

    # Observability
    otel_exporter_otlp_endpoint: str | None = None
    prometheus_enabled: bool = True

    # Cost engine (simulated pricing assumptions — not a real billing source)
    cost_cpu_core_hour_usd: float = 0.034
    cost_memory_gb_hour_usd: float = 0.0045
    cost_storage_gb_hour_usd: float = 0.0001


@lru_cache
def get_settings() -> Settings:
    return Settings()
