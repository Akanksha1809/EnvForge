# EnvForge Architecture

## System overview

```mermaid
flowchart TB
    subgraph Client
        Portal["Developer Portal\n(React + TS + Vite)"]
        GH["GitHub\n(PRs, webhooks, Actions)"]
    end

    subgraph EnvForge Platform
        API["FastAPI API\n(auth, RBAC, REST v1)"]
        DB[("PostgreSQL")]
        Redis[("Redis\n(broker + cache)")]
        Worker["Celery Worker\n(provisioning, lifecycle,\ncleanup, cost, github)"]
        Beat["Celery Beat\n(TTL sweep, orphan GC)"]
    end

    subgraph Infra["Provisioning targets"]
        TF["Terraform\n(namespace + app modules)"]
        K8s["Kubernetes\n(local kind today,\nEKS modules written, not run)"]
    end

    subgraph Observability
        Prom["Prometheus"]
        Graf["Grafana"]
        OTel["OpenTelemetry\ncollector/traces"]
    end

    Portal -->|REST + JWT| API
    GH -->|webhook| API
    API -->|commit status, comments| GH
    API --> DB
    API -->|enqueue job| Redis
    Worker --> Redis
    Worker --> DB
    Worker --> TF
    TF --> K8s
    Beat --> Redis
    API -.metrics.-> Prom
    Worker -.metrics.-> Prom
    Prom --> Graf
    API -.traces.-> OTel
    Worker -.traces.-> OTel
```

## Request / provisioning flow (target shape, built across Phases 2–3)

```mermaid
sequenceDiagram
    participant Dev as Developer / GitHub
    participant API as FastAPI
    participant DB as Postgres
    participant Q as Redis/Celery
    participant W as Worker
    participant TF as Terraform
    participant K8s as kind cluster

    Dev->>API: POST /environments (or PR opened webhook)
    API->>API: validate config, check RBAC + quotas
    API->>DB: insert Environment(REQUESTED), Job
    API->>Q: enqueue provisioning task
    API-->>Dev: 202 Accepted {environment_id, job_id}
    Q->>W: deliver task
    W->>DB: VALIDATING -> QUEUED -> PROVISIONING
    W->>TF: terraform apply (namespace + app modules)
    TF->>K8s: create namespace, deployment, service, ingress
    W->>DB: DEPLOYING -> HEALTH_CHECKING
    W->>K8s: poll readiness
    W->>DB: READY (+ preview_url)
    W-->>Dev: GitHub commit status / PR comment (if PR-triggered)
```

## Why these choices

- **FastAPI + async SQLAlchemy**: the API never blocks on provisioning —
  every mutating environment endpoint enqueues a Celery task and returns
  immediately, per the spec's "API should not block" requirement.
- **Domain logic lives in `app/services/*`, not in routers.** Routers stay
  thin (parse request → call service → map to response) so the lifecycle
  state machine, RBAC matrix, and provisioning pipeline are each testable in
  isolation and have exactly one implementation each.
- **Local JWT auth is always available**; GitHub OAuth activates only when
  `GITHUB_OAUTH_CLIENT_ID/SECRET` are configured. This means the whole
  platform is demoable with zero external accounts, while still having a
  real OAuth path for when it's configured.
- **Terraform + kubectl against a real local `kind` cluster**, not a mocked
  provisioner. The alternative (fake "provisioning" that just flips a
  database flag) would contradict the spec's explicit "do not implement
  fake integrations" requirement — so Phase 3 bootstraps an actual local
  Kubernetes cluster and applies actual Terraform against it.
- **Celery beat for TTL/cleanup** rather than a cron hitting an HTTP
  endpoint: keeps scheduling inside the same task infrastructure used for
  provisioning, so retries/backoff/observability are uniform.

See [`docs/roadmap.md`](roadmap.md) for phase-by-phase status and the
explicit list of what's simulated vs. real.
