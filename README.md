# EnvForge

A self-service **ephemeral environment management platform**: automatically
provisions isolated, production-like application environments for every
GitHub pull request, and lets developers create/inspect/manage environments
by hand through a developer portal.

This is a from-scratch, phase-by-phase build. See
[`docs/roadmap.md`](docs/roadmap.md) for what's implemented vs. planned, and
[`docs/architecture.md`](docs/architecture.md) for the system design.

## Status: Phase 1 — Foundation ✅

What works today, for real (no mocks):

- **Backend**: FastAPI + SQLAlchemy (async) + Alembic + PostgreSQL, local
  JWT auth (register/login/refresh/me) with RBAC roles
  (`platform_admin`/`team_admin`/`developer`/`viewer`), structured JSON
  logging, Prometheus `/metrics`, an audit log.
- **Worker**: Celery wired to Redis, connected and ready (no tasks yet —
  those land with provisioning in Phase 3).
- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS v4 developer
  portal shell — login/register, protected routing, a real dashboard shell
  authenticated against the live API.
- **Infra**: Docker Compose stack (Postgres, Redis, API, worker, frontend,
  Prometheus, Grafana); `kind`/`kubectl`/`helm`/`terraform` confirmed
  available locally for the real Kubernetes provisioning built in Phase 3.
- **CI**: GitHub Actions for backend (ruff, mypy, pytest w/ coverage against
  a real Postgres service container) and frontend (oxlint, vitest, build).

Everything else in the full spec (application registry, environment
lifecycle engine, provisioning, GitHub integration, cleanup/quotas/cost,
full dashboard, observability, cloud Terraform) is being built incrementally
— see the roadmap doc.

## Quick start

```bash
make setup   # install backend + frontend deps, create .env files
make dev     # docker compose up --build (postgres, redis, api, worker, frontend, prometheus, grafana)
make test    # run backend + frontend test suites
```

Once `make dev` is up:

- API: http://localhost:8010 (docs at `/api/docs`, health at `/health`, metrics at `/metrics`)
- Frontend: http://localhost:5173
- Grafana: http://localhost:3001 (anonymous viewer enabled)
- Prometheus: http://localhost:9090

> The API's host port defaults to **8010**, not 8000, because 8000 is a
> common conflict on developer machines (e.g. an existing SSH tunnel) —
> override with `API_HOST_PORT` in `.env` if needed.

The **first user you register becomes the platform admin**; everyone after
that defaults to `developer`.

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
