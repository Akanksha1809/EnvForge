# Sample App A — EnvForge demo backend

A minimal FastAPI service with Postgres + Redis, used to demonstrate the
`basic-backend` environment template. Not meant to be interesting on its
own — it exists so EnvForge has something real to provision.

- `GET /health` — checks both dependencies, returns `ok`/`degraded`.
- `GET /api/items`, `POST /api/items` — trivial Postgres-backed CRUD.
- `GET /api/hits` — Redis `INCR` counter.

## Run locally (no EnvForge needed)

```bash
docker run -d --name sample-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16-alpine
docker run -d --name sample-redis -p 6379:6379 redis:7-alpine
pip install -r requirements.txt
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres \
REDIS_URL=redis://localhost:6379/0 \
uvicorn app.main:app --reload
```

## Deployed by EnvForge

`scripts/register_sample_backend.py` registers this app (pointing at the
`envforge/sample-backend:dev` image — build it with `make
build-sample-backend`) so `POST /environments` provisions a real
namespace/deployment/service/ingress for it against the local `kind`
cluster. See `apps/api/tests/integration/test_provisioning_live.py` for
the automated version of the same flow.
