# EnvForge Build Roadmap

Built incrementally, one phase at a time, each verified (tests run, stack
booted, endpoints exercised) before moving on. This file is updated as each
phase lands.

| Phase | Scope | Status |
|---|---|---|
| 1 | Foundation: repo scaffold, FastAPI skeleton, Postgres+Alembic, local JWT auth + RBAC, Celery wiring, Docker Compose, React+Vite+Tailwind portal shell, CI | ✅ Done |
| 2 | Core platform: Application Registry, Teams, Environment Templates (versioned), Environment API + lifecycle state machine + event audit trail, Jobs API | ✅ Done |
| 3 | Provisioning: real Terraform modules + `kind` cluster, Celery provisioning pipeline, sample app A, end-to-end deploy to a live local cluster | ✅ Done |
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

## Phase 3 notes

- **Real infrastructure, genuinely verified**: Terraform modules
  (namespace+quota+limitrange+networkpolicy, app deployment+service+ingress,
  ephemeral dependencies) apply against a live local `kind` cluster with
  `ingress-nginx`, and a real sample app (FastAPI + Postgres + Redis) was
  deployed, health-checked via real `kubectl` pod-readiness polling, served
  real HTTP traffic through the real ingress at a real `nip.io` hostname,
  and torn down cleanly — see `tests/integration/test_provisioning_live.py`
  (excluded from the default test run via the `requires_kind` marker, since
  CI has no kind cluster; run it locally with `pytest -m requires_kind`).
- **Found and fixed while wiring this up**: `_prepare_workspace` initially
  copied only the root module's `.tf` files into each environment's
  workspace, breaking the modules' `../../modules/...` relative source
  paths. Fixed by mirroring the full `modules/` + `environments/local/`
  relative layout per workspace.
- **Found and fixed**: the dockerized worker's `terraform apply` kept
  failing against `host.docker.internal` in two stages — first a plain
  connection refusal (the Kubernetes provider reads `config_path` straight
  from a Terraform variable, so setting `KUBECONFIG` in the subprocess
  environment alone did nothing; fixed by passing the *patched* path as
  the tfvar), then an x509 error once connections actually landed: kind's
  API server certificate is only issued for
  `127.0.0.1`/`localhost`/the cluster's in-cluster hostnames, never
  `host.docker.internal`. The patched kubeconfig now sets
  `insecure-skip-tls-verify: true` for the rewritten cluster entry only —
  safe here specifically because this path exists solely to reach a local
  `kind` cluster through the Docker host gateway, and a real/cloud
  target's kubeconfig is never touched by this code at all.
- **Found and fixed**: the environment-app module's `preview_url` output
  omitted the ingress's host port, which would have produced an
  unreachable URL (kind maps the ingress to `18080`, not `80`) — added an
  `ingress_port` variable threaded through from `app/core/config.py`.
- **Found and fixed**: the dockerized API/worker's bind-mounted `--reload`
  silently stopped picking up code changes partway through this phase (a
  Colima/virtiofs quirk — neither inotify nor watchfiles' polling fallback
  worked reliably, and polling additionally nearly hung scanning the
  bind-mounted `.venv`). Removed `--reload` entirely for these two
  containers; local backend changes now need an explicit `make restart`.
  This is called out here because it's exactly the kind of thing that
  could otherwise make "it works on my machine" silently stop being true.
- Provisioning runs through two possible Celery workers in local dev: the
  dockerized `worker` service (reaches `kind` via `host.docker.internal`,
  with a kubeconfig rewrite — see
  `provisioning._effective_kubeconfig_path`) or `make worker-host` (runs
  directly on the host, which reaches `kind` the same way `kubectl` does).
  Either is sufficient; both can run at once since they share one queue.
- Environment deletion now actually destroys infrastructure: if an
  environment has a `namespace` (i.e. it was really provisioned),
  `DELETE /environments/{id}` dispatches a real `terraform destroy` job
  and the environment sits in `DELETING` until that succeeds — it is never
  marked `DELETED` on a destroy failure, so cleanup can retry safely.
- Observed (not a code bug): on a heavily-loaded shared dev machine running
  several unrelated kind clusters at once, `kube-controller-manager` and
  `kube-scheduler` themselves can crash-loop from failed liveness probes
  under CPU starvation, stalling every Deployment in the cluster — not
  just EnvForge's. `terraform apply`'s `wait_for_rollout` simply keeps
  waiting (up to its own timeout) and the task's exception handling
  transitions the environment to `FAILED` with a clear error if it never
  recovers in time — the same designed-for failure path as any other
  provisioning error, which is itself a reasonable demonstration of it
  working as intended.

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
