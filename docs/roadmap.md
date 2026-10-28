# EnvForge Build Roadmap

Built incrementally, one phase at a time, each verified (tests run, stack
booted, endpoints exercised) before moving on. This file is updated as each
phase lands.

| Phase | Scope | Status |
|---|---|---|
| 1 | Foundation: repo scaffold, FastAPI skeleton, Postgres+Alembic, local JWT auth + RBAC, Celery wiring, Docker Compose, React+Vite+Tailwind portal shell, CI | ✅ Done |
| 2 | Core platform: Application Registry, Teams, Environment Templates (versioned), Environment API + lifecycle state machine + event audit trail, Jobs API | ✅ Done |
| 3 | Provisioning: real Terraform modules + `kind` cluster, Celery provisioning pipeline, sample apps A/B/C, end-to-end deploy to a live local cluster | ⏳ Next |
| 4 | GitHub integration: webhooks, signature verification, PR open/sync/close handling, commit statuses, preview URLs, webhook simulator | Planned |
| 5 | Environment management: TTL expiration, cleanup/GC engine, resource quotas, retry/recovery, extend/refresh | Planned |
| 6 | Developer portal: full dashboard, catalogs, environment detail, templates UI, team management, audit history — wired to real data only | Planned |
| 7 | Observability & security hardening: OpenTelemetry tracing, Grafana dashboards/alerts, container scanning in CI, RBAC test depth | Planned |
| 8 | Advanced features: cost estimation engine, template versioning UX, environment cloning, optimization recommendations, AWS Terraform (written, not executed) | Planned |
| 9 | Production-style validation: full test pyramid incl. e2e + failure injection, Terraform/Helm validation in CI, `scripts/demo.sh`, final docs pass | Planned |

## Phase 2 notes

- The lifecycle state machine (`app/services/lifecycle.py`) allows cancelling
  straight to `DELETING` from any in-flight state, not only from `READY` or
  `FAILED` — a user can tear down an environment mid-provisioning. This was
  caught by an integration test exercising the full create→extend→delete
  flow against a `QUEUED` environment and fixed before Phase 2 was marked
  done.
- `POST /environments` enqueues a `Job` row (`provision`, `PENDING`) but does
  **not** yet dispatch a Celery task — there is no task to dispatch to until
  Phase 3 adds the provisioning pipeline. The environment sits at `QUEUED`
  honestly rather than faking progress.
- `GET /environments/{id}/logs` derives log-shaped lines from the lifecycle
  event history rather than returning fabricated container output — real
  log streaming depends on the Kubernetes provisioning Phase 3 adds.

## Known, deliberate simplifications

- **Kubernetes target is local `kind`, not AWS EKS.** Provisioning is real
  (real `terraform apply`, real namespaces/pods), just against a local
  cluster. AWS Terraform modules exist for the cloud path but are never
  executed in this environment (no AWS credentials).
- **GitHub webhooks are triggered by a local simulator script**, since this
  sandbox has no public URL for github.com to call. The webhook handler
  itself — signature verification, idempotency, PR state handling — is the
  real code path; only the transport is simulated for local dev.
- **Cost figures are `estimated`/`simulated`**, never real cloud billing —
  there is no billing API integration.
