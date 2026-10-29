# EnvForge

A self-service **ephemeral environment management platform**: automatically
provisions isolated, production-like application environments for every
GitHub pull request, and lets developers create/inspect/manage environments
by hand through a developer portal.

This is a from-scratch, phase-by-phase build. See
[`docs/roadmap.md`](docs/roadmap.md) for what's implemented vs. planned, and
[`docs/architecture.md`](docs/architecture.md) for the system design.

## Status: Phases 1–8 done ✅ (of 9)

What works today, for real (no mocks):

- **Backend**: FastAPI + SQLAlchemy (async) + Alembic + PostgreSQL, local
  JWT auth with RBAC roles (`platform_admin`/`team_admin`/`developer`/
  `viewer`), structured JSON logging, Prometheus `/metrics`, an audit log.
- **Core platform**: Application Registry, Teams, versioned Environment
  Templates, a real environment lifecycle state machine with a persisted
  event audit trail, and a Jobs API — all behind REST v1 endpoints with
  pagination/filtering/sorting.
- **Provisioning**: real Terraform modules (namespace isolation with
  ResourceQuota/LimitRange/NetworkPolicy, app deployment+service+ingress,
  ephemeral dependencies) applied by a Celery pipeline against a live
  local `kind` cluster — verified end-to-end (deploy, real `kubectl`
  health check, real HTTP traffic through real ingress, clean teardown)
  in `apps/api/tests/integration/test_provisioning_live.py`.
- **GitHub integration**: a real webhook endpoint with HMAC-SHA256
  signature verification and delivery-id idempotency, full PR
  open/synchronize/closed handling (redeploy in place, never a duplicate
  environment), and real commit-status/PR-comment posting (a no-op until
  `GITHUB_API_TOKEN` is configured — see below).
- **Environment management**: a real Celery Beat process runs TTL
  expiration, orphaned-namespace detection, and stale-job detection on
  independent schedules; quotas enforced per user/application/team;
  `POST /jobs/{id}/retry` actually re-dispatches the failed task;
  `POST /environments/{id}/expire` is the manual cleanup control.
- **Developer portal**: React 19 + TypeScript + Vite + Tailwind CSS v4 —
  a real dashboard (live aggregate counts + recharts charts + recent
  jobs, from `GET /dashboard/summary`), Application/Environment/Template/
  Team catalogs, an environment detail page with its full lifecycle
  event timeline and logs, and a platform-admin audit history view.
  Every page reads real data; there is no mock data in the portal.
- **Observability**: Prometheus metrics computed from live DB state (not
  fake counters), a real provisioned Grafana dashboard (9 panels — stats,
  a gauge, two timeseries) and 5 Prometheus alert rules covering failure
  rate, job backlog, and stuck provisioning, plus OpenTelemetry tracing
  wired into both the API and the Celery worker.
- **Security**: a full RBAC permission matrix enforced server-side and
  locked in by tests at both the unit and API level, and Trivy container
  scanning in CI against the real built `api`/`worker`/`frontend` images.
- **Infra**: Docker Compose stack (Postgres, Redis, API, worker, beat,
  frontend, Prometheus, Grafana) plus a real local `kind` cluster with
  `ingress-nginx`.
- **CI**: GitHub Actions for backend, frontend, and Terraform (fmt/validate
  across all modules, including the AWS ones below), plus container image
  scanning.
- **Advanced features**: a cost-estimation engine (`estimated` when an
  application's real resource requests are known, honestly `simulated`
  otherwise — never claimed as real cloud billing), one-click environment
  cloning (`POST /environments/{id}/clone`), resource-optimization
  recommendations derived from live platform state (quota pressure, stale
  environments, missing config, exhausted job retries), and a full,
  `terraform validate`-clean AWS cloud Terraform module (VPC/EKS/RDS/
  ElastiCache/ECR/IRSA) — written, validated, plan-checked, and
  **deliberately never applied**; see
  [`docs/cloud-deployment.md`](docs/cloud-deployment.md).

Everything else (e2e tests, the final demo script) is being built
incrementally — see [`docs/roadmap.md`](docs/roadmap.md) for the full
phase-by-phase status and every bug found/fixed along the way.

## Quick start

```bash
make setup   # install backend + frontend deps, create .env files
make dev     # docker compose up --build (postgres, redis, api, worker, frontend, prometheus, grafana)
make test    # run backend + frontend test suites
```

Once `make dev` is up:

- API: http://localhost:8010 (docs at `/api/docs`, health at `/health`, metrics at `/metrics`)
- Frontend: http://localhost:5173
- Grafana: http://localhost:3001 (anonymous viewer enabled — open the
  "EnvForge Platform" dashboard)
- Prometheus: http://localhost:9091

> Several host ports default away from their usual numbers (API **8010**
> not 8000, Prometheus **9091** not 9090) because those are common
> conflicts on developer machines (existing SSH tunnels, other local
> Prometheus instances, etc). Override via `API_HOST_PORT`,
> `PROMETHEUS_HOST_PORT`, or `GRAFANA_HOST_PORT` in `.env` if needed.

The **first user you register becomes the platform admin**; everyone after
that defaults to `developer`.

## Try real provisioning (Phase 3)

```bash
make kind-up            # bootstrap a local kind cluster
make kind-ingress       # install ingress-nginx into it
make build-sample-backend  # build + load the sample app image into kind
python scripts/register_sample_backend.py   # registers it as an EnvForge application
```

Then `POST /api/v1/environments` (or use the curl command the script
prints) and watch `kubectl get pods -A` — a real namespace, deployment,
service and ingress get created, health-checked, and served over HTTP.

## Try the GitHub integration (Phase 4)

No real GitHub App needed — `scripts/simulate_webhook.py` posts
correctly HMAC-signed `pull_request` payloads straight at the real
webhook endpoint (the handler code is identical to what a real
`github.com` delivery would hit):

```bash
# Register an application with github_repo set first, then:
python scripts/simulate_webhook.py opened --repo acme/sample-backend --pr 42
python scripts/simulate_webhook.py synchronize --repo acme/sample-backend --pr 42
python scripts/simulate_webhook.py closed --repo acme/sample-backend --pr 42
```

Set `GITHUB_API_TOKEN` in `.env` against a real repo to have EnvForge
actually post commit statuses and PR comments — without it, those calls
are logged no-ops rather than fabricated successes.

## Repository layout

```
apps/api/             FastAPI app, Celery worker, Alembic migrations,
                       tests (unit/, integration/, e2e/)
apps/frontend/         React + TypeScript + Vite + Tailwind developer portal
infrastructure/        Terraform modules (local kind + AWS), kind/k8s config
sample-apps/backend/   The one demo application EnvForge actually provisions
observability/        Prometheus config, Grafana dashboards/alerts
scripts/                demo.sh, webhook simulator, sample-app registration
docs/                  Architecture, ADRs, diagrams, guides
.github/workflows/     CI
```

Two things the original scaffold planned but this build never populated,
removed rather than left as empty placeholders: a top-level `templates/`
directory (environment templates are real, versioned, and live entirely
in the database via the `POST /templates` API — never files on disk, so
there was nothing to put there), and `sample-apps/fullstack|microservices`
(only the backend sample app was ever built; see **Future enhancements**
below).

No Helm charts: `ingress-nginx` is installed with its own plain `kubectl
apply` manifest (see `make kind-ingress`), and every other Kubernetes
object EnvForge creates goes through the Terraform modules above instead
— there was never a second packaging layer to add on top of that.

## Local vs. cloud

Kubernetes/Terraform provisioning in this project targets a **local `kind`
cluster** by default — genuinely real infrastructure automation, just not
AWS. The AWS/EKS Terraform modules (Phase 8) are written, `terraform
validate`-clean, and plan-checked, but intentionally **never applied**
here — a deliberate project policy against creating real, billable cloud
infrastructure, not a limitation of missing credentials. See
[`docs/cloud-deployment.md`](docs/cloud-deployment.md).

## Demo

```bash
make kind-up && make kind-ingress && make build-sample-backend && make dev
make demo
```

`scripts/demo.sh` walks the full platform end to end against the real,
running stack: registers a sample application, provisions a real preview
environment (real `terraform apply`, real `kubectl` health check against
`kind`), checks its cost estimate, queries the platform-wide cost summary
and optimization recommendations, clones it, exercises a full GitHub PR
open/sync/close lifecycle through the real webhook handler (correctly
HMAC-signed payloads standing in for GitHub's own delivery, since this
sandbox has no public URL for github.com to call), then tears down what it
created. Every step calls the real API; nothing is mocked except noted.
On a heavily loaded host, step 4 (waiting for `READY`) can occasionally
see a `FAILED` environment instead, with a real Terraform error about the
`kind` control plane timing out under CPU contention — that's the
lifecycle's failure handling working correctly under real infrastructure
stress, not a code bug; rerunning `make demo` on a quieter host reaches
`READY`.

## Testing

```bash
make test-backend   # pytest: unit + integration + e2e (requires_kind-marked tests excluded by default)
make test-frontend  # vitest
```

The backend suite includes dedicated failure-injection tests
(`tests/unit/test_provisioning_task_failures.py` — Terraform apply
failures, health-check timeouts, and failed teardowns, asserting the
environment lands in the correct state rather than a falsely successful
one) and a full-platform `tests/e2e/test_full_platform_flow.py` that
drives one environment through registration, real provisioning (mocked
Terraform/kubectl calls, real state machine), cost, recommendations,
extension, cloning, and teardown in a single run. `pytest -m
requires_kind` additionally runs `tests/integration/test_provisioning_live.py`
against a real local `kind` cluster when one is available (excluded from
the default run and from CI, which has none).

## Limitations

- **AWS Terraform is written and validated, never applied** — see
  [`docs/cloud-deployment.md`](docs/cloud-deployment.md).
- **GitHub integration's transport is simulated locally**
  (`scripts/simulate_webhook.py`); the webhook handler itself (signature
  verification, idempotency, PR state handling) is the real code path.
- **Cost figures are `estimated`/`simulated`**, never real cloud billing.
- **No Helm charts** — `ingress-nginx` installs from a plain manifest, and
  every other Kubernetes object goes through the Terraform modules instead.
- **Single-region, single-cluster local target** — no multi-region or
  multi-cluster support, matching a single local `kind` cluster's scope.
- See [`docs/roadmap.md`](docs/roadmap.md)'s "Known, deliberate
  simplifications" section for the complete, maintained list.

## Future enhancements

- Finish wiring GitHub OAuth as a first-class login option in the portal
  (the backend path exists; the frontend only has local email/password).
- Team-scoped role management over the API (currently platform roles are
  set at registration; per-team role changes aren't yet exposed).
- Apply the AWS Terraform module against a real account, then point
  `app/services/provisioning.py` at it instead of `kind` — see
  `docs/cloud-deployment.md`'s prerequisites section for what that needs.
- A second sample app exercising a `fullstack` or `microservices`
  `EnvironmentTemplate` (only `basic_backend`, via the one backend sample
  app, was ever built) to prove out multi-service dependency provisioning
  beyond the single-app + Postgres + Redis shape this build demonstrates.
