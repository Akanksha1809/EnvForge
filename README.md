# EnvForge

A self-service **ephemeral environment management platform**: automatically
provisions isolated, production-like application environments for every
GitHub pull request, and lets developers create/inspect/manage environments
by hand through a developer portal.

This is a from-scratch, phase-by-phase build. See
[`docs/roadmap.md`](docs/roadmap.md) for what's implemented vs. planned, and
[`docs/architecture.md`](docs/architecture.md) for the system design.

## Status: Phases 1–7 done ✅ (of 9)

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
  across all four modules), plus container image scanning.

Everything else (the cost engine, cloud Terraform, e2e tests, the final
demo script) is being built incrementally — see
[`docs/roadmap.md`](docs/roadmap.md) for the full phase-by-phase status
and every bug found/fixed along the way.

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
apps/api/            FastAPI app, Celery worker, Alembic migrations, tests
apps/frontend/        React + TypeScript + Vite + Tailwind developer portal
infrastructure/       Terraform modules, kind/k8s config, Helm charts
templates/            Versioned environment template definitions
sample-apps/          The 3 demo applications EnvForge provisions
observability/        Prometheus config, Grafana dashboards/alerts
tests/e2e, tests/performance
scripts/               demo.sh, webhook simulator, seed data
docs/                 Architecture, ADRs, diagrams, guides
.github/workflows/    CI
```

## Local vs. cloud

Kubernetes/Terraform provisioning in this project targets a **local `kind`
cluster** by default — genuinely real infrastructure automation, just not
AWS. The AWS/EKS Terraform modules (Phase 8/9) are written and documented
but intentionally **not executed** here, since this environment has no AWS
account or credentials. See `docs/cloud-deployment.md` once it lands.
