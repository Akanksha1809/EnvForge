.PHONY: setup dev dev-down test test-backend test-frontend lint fmt migrate demo kind-up kind-down logs

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

kind-down:
	kind delete cluster --name envforge

## Run the full reproducible demo scenario end-to-end (see scripts/demo.sh).
demo:
	bash scripts/demo.sh
