.PHONY: setup dev dev-down restart test test-backend test-frontend lint fmt migrate demo kind-up kind-down kind-ingress logs worker-host build-sample-backend

COMPOSE := docker-compose

## One-time local setup: install dependencies for backend + frontend.
setup:
	cd apps/api && uv venv .venv --python 3.12 && uv pip install -e . --group dev -p .venv/bin/python
	cd apps/frontend && npm install
	test -f .env || cp .env.example .env
	test -f apps/frontend/.env || cp apps/frontend/.env.example apps/frontend/.env

## Bring up the full local stack (Postgres, Redis, API, worker, frontend, Prometheus, Grafana).
dev:
	$(COMPOSE) up -d --build

dev-down:
	$(COMPOSE) down

## The api/worker containers don't auto-reload (see docker-compose.yml) —
## run this after changing backend code.
restart:
	$(COMPOSE) build api worker && $(COMPOSE) up -d api worker

logs:
	$(COMPOSE) logs -f api worker

## Run every automated test suite.
test: test-backend test-frontend

test-backend:
	cd apps/api && .venv/bin/python -m pytest tests/ -v

test-frontend:
	cd apps/frontend && npm run test

lint:
	cd apps/api && .venv/bin/python -m ruff check app/ tests/ && .venv/bin/python -m mypy app/
	cd apps/frontend && npm run lint

fmt:
	cd apps/api && .venv/bin/python -m ruff format app/ tests/

## Apply database migrations against the running Postgres container.
migrate:
	cd apps/api && .venv/bin/python -m alembic upgrade head

## Bootstrap the local kind cluster used for real provisioning (Phase 3+).
kind-up:
	kind create cluster --name envforge --config infrastructure/kubernetes/kind-cluster.yaml

## Install ingress-nginx into the kind cluster (run once after kind-up).
kind-ingress:
	kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.3/deploy/static/provider/kind/deploy.yaml
	kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=180s

kind-down:
	kind delete cluster --name envforge

## Build a sample app image and load it into the kind cluster so EnvForge
## can actually deploy it (`kind load` makes it available to the cluster
## without pushing to a registry).
build-sample-backend:
	docker build -t envforge/sample-backend:dev sample-apps/backend
	kind load docker-image envforge/sample-backend:dev --name envforge

## Run a Celery worker directly on the host rather than in Docker. Needed
## for real provisioning if the dockerized `worker` service's
## host.docker.internal path to the kind cluster isn't reachable on your
## setup — a host process reaches `kind` exactly like your own `kubectl` does.
worker-host:
	cd apps/api && .venv/bin/celery -A app.workers.celery_app worker --loglevel=info

## Run the full reproducible demo scenario end-to-end (see scripts/demo.sh).
demo:
	bash scripts/demo.sh
