# EnvForge Build Roadmap

Built incrementally, one phase at a time, each verified (tests run, stack
booted, endpoints exercised) before moving on. This file is updated as each
phase lands.

| Phase | Scope | Status |
|---|---|---|
| 1 | Foundation: repo scaffold, FastAPI skeleton, Postgres+Alembic, local JWT auth + RBAC, Celery wiring, Docker Compose, React+Vite+Tailwind portal shell, CI | ✅ Done |
| 2 | Core platform: Application Registry, Teams, Environment Templates (versioned), Environment API + lifecycle state machine + event audit trail, Jobs API | ✅ Done |
| 3 | Provisioning: real Terraform modules + `kind` cluster, Celery provisioning pipeline, sample app A, end-to-end deploy to a live local cluster | ✅ Done |
| 4 | GitHub integration: webhooks, signature verification, PR open/sync/close handling, commit statuses, preview URLs, webhook simulator | ✅ Done |
| 5 | Environment management: TTL expiration, cleanup/GC engine, resource quotas, retry/recovery, extend/refresh | ✅ Done |
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

## Phase 4 notes

- The lifecycle table gained two more edges: `READY -> PROVISIONING` and
  `FAILED -> PROVISIONING`, both for the same reason — a new commit
  pushed to an already-provisioned (or previously-failed) PR redeploys
  in place via `environments_service.redeploy_for_new_commit` rather
  than creating a second environment for the same PR. `terraform apply`
  against the existing per-environment workspace/state is idempotent, so
  this is a real redeploy, not a relabeled fresh provision.
- Idempotency is enforced at two levels: `WebhookDelivery` dedupes by
  GitHub's own `X-GitHub-Delivery` id (so a redelivered webhook — GitHub
  retries on timeout/5xx — is a no-op), and `get_active_environment_for_pr`
  means even a semantically-duplicate event (e.g. `synchronize` arriving
  before `opened`, or `opened` redelivered under a new delivery id for
  some reason) still can't create a second environment for one PR. Both
  are exercised in `tests/integration/test_github_webhook_api.py`.
- A redeploy skips re-dispatching a new Terraform run while one is
  already in flight for that environment (QUEUED/PROVISIONING/DEPLOYING/
  HEALTH_CHECKING) — the per-environment Terraform state has no locking,
  so two concurrent `apply`s against it would race. The commit SHA is
  still updated immediately; only the Terraform run is deferred.
- GitHub API calls (commit statuses, PR comments) go through
  `app/services/github_client.py`, which is a real HTTP client against
  the real GitHub REST API — but every call is a logged no-op when
  `GITHUB_API_TOKEN` isn't set, which is the default here (no real GitHub
  App/PAT in this sandbox). Configure a token against a real repo and the
  exact same code starts actually posting.
- `scripts/simulate_webhook.py` signs payloads with the real HMAC
  verification this project's own webhook endpoint checks — the handler
  code path (signature check, idempotency, PR state machine) is 100% real;
  only GitHub's own delivery transport is stood in for, since this sandbox
  has no public URL for github.com to call.

## Phase 5 notes

- A real `beat` process (separate container/process from `worker` — beat
  only *schedules*, never executes) runs three independent sweeps on
  their own intervals: TTL expiration, orphaned-namespace detection, and
  stale-job detection. Each is idempotent and safe to overlap with itself.
- **Quotas** are enforced at three scopes — per user
  (`max_active_environments_per_user`, global setting), per application
  (`Application.max_active_environments`, optional override, `None` =
  inherit the team's), and per team (`Team.max_active_environments`,
  already built in Phase 2) — all in `app/services/quotas.py`, checked
  together in `create_environment` via `check_all_quotas`. CPU/memory/
  storage limits remain enforced at the Kubernetes level (each
  environment's namespace ResourceQuota, Phase 3) — this module is only
  about *how many* environments can exist at once.
- **Found and fixed**: `POST /jobs/{id}/retry` reset a job's status to
  `PENDING` but never actually re-dispatched the Celery task — so
  "retrying" a failed job silently did nothing until something else
  happened to re-trigger it. Fixed to redispatch the correct task
  (`provision_environment` or `destroy_environment`, by `job_type`) and
  land on `QUEUED` with a `celery_task_id` when dispatch succeeds, the
  same contract `create_environment`/`request_deletion` already use.
- **Orphan detection** is honest about scope: a namespace is "orphaned"
  only when no non-terminal Environment row claims it (cross-referenced
  by the `envforge.io/environment` label every namespace carries — see
  the environment-namespace Terraform module, Phase 3). When a matching
  Environment row exists but is terminal (e.g. a destroy that previously
  failed partway), cleanup goes through `terraform destroy` against its
  real workspace/state rather than a blunt `kubectl delete namespace`, so
  Terraform's own state stays consistent; a true orphan (no row at all)
  falls back to deleting the namespace directly since there's no
  Terraform state to reconcile against.
- **Stale job detection** exists because a worker process can simply die
  mid-task (OOM-killed, container restart) leaving a `Job` stuck
  `RUNNING` forever with nothing to ever mark it otherwise. The threshold
  (`stale_job_timeout_minutes`, default 35) is deliberately set above
  Celery's own `task_time_limit` (30 min) — if a job is still `RUNNING`
  past that, the worker that owned it is gone, not just slow.
- The lifecycle table now lets *any* non-terminal, non-`DELETING` state
  transition to `EXPIRED` (previously only `READY` could) — an
  environment stuck mid-provisioning past its TTL needs to expire too,
  not just one that made it all the way to `READY`.
- `POST /environments/{id}/expire` is the manual cleanup control the spec
  asks for: force an environment through the same expire-then-delete path
  the TTL sweep uses, on demand, without waiting for the schedule.

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
