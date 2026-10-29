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
| 6 | Developer portal: full dashboard, catalogs, environment detail, templates UI, team management, audit history — wired to real data only | ✅ Done |
| 7 | Observability & security hardening: OpenTelemetry tracing, Grafana dashboards/alerts, container scanning in CI, RBAC test depth | ✅ Done |
| 8 | Advanced features: cost estimation engine, template versioning UX, environment cloning, optimization recommendations, AWS Terraform (written, not executed) | ✅ Done |
| 9 | Production-style validation: full test pyramid incl. e2e + failure injection, Terraform validation in CI, `scripts/demo.sh`, final docs pass | ✅ Done |

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

## Phase 6 notes

- Two small backend additions landed alongside the frontend because the
  portal genuinely needed them: `GET /dashboard/summary` (real aggregate
  SQL — counts by state, by application, by team, provisioning success
  rate and average duration from real Job rows — no cost figures, that's
  explicitly Phase 8's job) and `GET /audit-logs` (paginated, platform-
  admin only) so the audit trail every service already wrote via
  `app.services.audit.record()` was actually readable from somewhere.
- Every page fetches real data via React Query against the live API —
  there is no mock data anywhere in the portal, including the empty
  states (e.g. "Cost engine lands in a later phase" rather than a
  fabricated dollar figure).
- Caught and fixed three real UI bugs while reviewing in the browser
  against the live stack (not just the automated test suite): a `Button`
  whose text wrapped onto two lines inside its own fixed height instead
  of staying on one line (`whitespace-nowrap`); page headers using
  `flex items-center justify-between` that overflowed off-screen on
  narrower viewports instead of wrapping (`flex-wrap gap-4`); and data
  tables using `overflow-hidden` on their container, which clips wide
  content instead of letting it scroll (`overflow-x-auto`). All three
  were verified fixed by re-screenshotting in the browser, not assumed.
- No dedicated Jobs page yet — the Jobs API (list/get/retry) is wired up
  in `api/jobs.ts` and used on the dashboard's "recent jobs" table, but a
  full jobs catalog view with retry buttons is a reasonable follow-up,
  not something this phase claims to have shipped.
- Team membership shows raw user IDs rather than names/emails — the
  `TeamMembership` schema only returns `user_id`, not a joined user
  record. A `GET /teams/{id}/members` enrichment (or a `/users` lookup
  endpoint) is a natural follow-up, not done here.

## Phase 7 notes

- **Prometheus metrics are computed from live DB state at scrape time**
  (`app/services/metrics.py`), not from in-process counters incremented
  by the worker — Prometheus can't scrape the worker process directly
  without a second exporter or multiprocess-mode coordination, and
  querying the same `environments`/`jobs` tables the REST API already
  reads is simpler and can't drift from reality. Verified live: the
  Grafana dashboard's "Active environments" stat matched
  `GET /dashboard/summary`'s `active_environments` exactly.
- **Grafana dashboard and Prometheus alert rules are real, checked-in
  config**, not a bare `docker-compose up` with nothing behind it —
  `observability/grafana/dashboards/envforge-platform.json` (9 panels:
  stats, a gauge, two timeseries) and
  `observability/prometheus/alerts/envforge-alerts.yml` (5 alert rules
  covering failure rate, queue backlog, stuck provisioning, and HTTP
  5xx). Verified by loading the dashboard in a browser against the live
  stack and confirming Prometheus reports every rule as `health: ok`
  via its own `/api/v1/rules` endpoint.
- **OpenTelemetry tracing** is wired into both the API
  (`FastAPIInstrumentor`) and the Celery worker (`CeleryInstrumentor`),
  exporting to a real OTLP collector when `OTEL_EXPORTER_OTLP_ENDPOINT`
  is configured, or to the console otherwise — consistent with this
  project's rule that an absent external dependency makes an integration
  a visible no-op, never silently nothing. Caught and fixed a real
  ordering bug while wiring this up: the worker's tracer setup lived at
  module level in `celery_app.py`, which the API process also imports
  (for `task_dispatch.enqueue`) — whichever process imported it first
  would win the race to set the global tracer provider's service name,
  mislabeling the other process's spans. Fixed by moving worker-only
  setup behind Celery's `worker_process_init` signal, which only fires
  inside an actual `celery worker` process.
- **Container image scanning** (Trivy, `CRITICAL,HIGH`, unfixed CVEs
  ignored) runs in CI against the real built `api`, `worker`, and
  `frontend` images — immutable `${{ github.sha }}` tags, never `latest`
  as the only reference.
- **RBAC test depth**: `tests/unit/test_rbac_matrix.py` locks in the
  full permission matrix per role (so a change to one role's permissions
  can't silently drift another's without a test failing), and
  `tests/integration/test_rbac_depth.py` exercises the same matrix
  through the real API — including the case that actually matters most:
  a user with a permission *globally* (e.g. `developer` has
  `ENVIRONMENT_CREATE`) is still blocked if they aren't a member of the
  team that owns the resource.

## Phase 8 notes

- **Cost estimation** (`app/services/cost_engine.py`) derives CPU/memory
  from an application's own `resource_requirements` when configured
  (basis `"estimated"`), or falls back to a documented default shape
  (basis `"simulated"`) when it isn't — never silently guessing without
  saying so. `GET /environments/{id}/cost` and `GET
  /dashboard/cost-summary` (grouped by team and application) are both
  live-verified against the real Docker stack. **Found and fixed while
  wiring this up**: the SQLite test database (used by `pytest`, see
  `tests/conftest.py`) strips `tzinfo` from `DateTime(timezone=True)`
  columns on round-trip, while Postgres preserves it — `created_at`/
  `destroyed_at` are normalized to UTC-aware before subtracting, so the
  same code is correct against both.
- **Environment cloning** (`POST /environments/{id}/clone`,
  `app/services/environments.clone_environment`) creates a brand-new
  environment for the same application from the source's config
  snapshot, but never copies its PR linkage — a clone is always a
  manual, `EventTrigger.USER` environment, so cloning a PR preview can't
  accidentally create a second environment GitHub's webhook handler
  thinks it owns. Goes through the same `create_environment` path as
  every other environment, so it's subject to the same quota checks
  (verified by `test_clone_respects_team_quota`).
- **Optimization recommendations** (`GET /dashboard/recommendations`,
  `app/services/recommendations.py`) are each derived from a real query
  against live platform state — team quota pressure (≥80% of
  `max_active_environments`), applications missing
  `resource_requirements` or an `environment_template_id`, environments
  active for more than 7 days, and jobs that exhausted their retries —
  never a canned or hardcoded tip. Verified live: a freshly registered
  user immediately sees real `cost_accuracy`/`consistency`
  recommendations for this stack's own pre-existing sample applications.
- **Template versioning UX**: the versioning API itself
  (`POST`/`GET /templates/{slug}/versions`) existed since Phase 2; Phase
  8 added the frontend — a "Version history" view per template card
  (`apps/frontend/src/pages/TemplatesPage.tsx`) listing every version
  with its `is_latest` badge, and a "New version" form that calls the
  same endpoint, so creating v2 of a template no longer requires `curl`.
- **AWS Terraform** (`infrastructure/terraform/modules/aws-platform`):
  VPC, EKS (one managed node group, OIDC/IRSA for the AWS Load Balancer
  Controller), RDS Postgres, ElastiCache Redis, three ECR repositories.
  `terraform init -backend=false && terraform validate` passes against
  it and the new `environments/aws` root module, and a one-off
  `terraform plan` (never `apply`) confirmed the plan itself resolves
  cleanly end-to-end. `apply` was never attempted and never will be as
  part of this project — a deliberate policy against creating real,
  billable cloud infrastructure with no one asking for it, not merely a
  side effect of missing credentials. See
  `infrastructure/terraform/modules/aws-platform/README.md` and
  `docs/cloud-deployment.md` (cost estimate, prerequisites, teardown
  procedure) for the rest.

## Phase 9 notes

- **Failure-injection tests**
  (`apps/api/tests/unit/test_provisioning_task_failures.py`) exercise the
  real Celery task coroutines (`_provision_environment`,
  `_destroy_environment`) against a real in-memory DB and the real
  lifecycle state machine, with only the Terraform/kubectl calls mocked.
  They assert the specific failure contract the spec requires: a
  Terraform apply failure or a health-check timeout lands the environment
  in `FAILED` with the real error message preserved (never silently
  stuck or falsely `READY`), and a failed teardown leaves the environment
  in `DELETING` rather than lying about `DELETED` — the exact behavior
  `app/workers/tasks/provisioning.py`'s comments already promised, now
  locked in by a test.
- **A full-platform e2e test**
  (`apps/api/tests/e2e/test_full_platform_flow.py`) is the one place that
  drives a single environment through every subsystem in the order a
  real user would — register, team, template, application, environment
  create, real provisioning pipeline to `READY` (Terraform/kubectl
  mocked, state machine real), cost, dashboard summary, cost summary,
  recommendations, extend, clone, teardown, and the audit trail — rather
  than each subsystem only ever being tested in isolation.
- **`scripts/demo.sh`** runs the same kind of flow against the actually
  running Docker Compose stack, with nothing mocked except GitHub's
  delivery transport (called out explicitly in its own output). Running
  it live surfaced two real, fixed issues before it's considered done:
  (1) it assumed `register_sample_backend.py` always sets the sample
  app's `github_repo`, which is only true on first creation — a stack
  with a pre-existing app from earlier manual testing had it `null`,
  making the webhook step silently say "ignored"; fixed by having the
  script read the app's actual `github_repo` and `PATCH` it in if unset,
  rather than assuming. (2) On this project's shared, contended sandbox,
  a `terraform apply` genuinely failed once with a live TLS handshake
  timeout against the `kind` API server and a connection-refused from
  the `ingress-nginx` admission webhook — the `kind` control plane itself
  starved of CPU by other concurrent processes on the host, not a code
  bug. The environment correctly landed in `FAILED` with that real error
  preserved. `scripts/demo.sh` now explains this directly in its own
  output instead of only pointing at "the cluster isn't up yet," and a
  rerun on a quieter host reached `READY` end to end, including a real
  HTTP response from the preview URL.
- **Terraform validation in CI**: the existing `fmt`/`init`/`validate`
  matrix (`.github/workflows/infrastructure.yml`) now covers all six
  Terraform roots, including the two added in Phase 8
  (`modules/aws-platform`, `environments/aws`). There is no Helm
  validation job — Phase 9 removed the placeholder one along with the
  empty `infrastructure/helm/` directory it was guarding, since this
  project never adopted Helm (`ingress-nginx` installs from a plain
  `kubectl apply` manifest, and every other Kubernetes object goes
  through the Terraform modules instead) and keeping a job that only
  ever prints "no charts yet" is exactly the kind of placeholder the
  spec asks not to leave lying around.
- **Final docs/repo cleanup**: removed two more empty, never-populated
  scaffold directories found during this pass — a top-level `templates/`
  (environment templates are real, versioned, and live entirely in the
  database via `POST /templates`; there was never a file to put there)
  and `sample-apps/fullstack`/`sample-apps/microservices` (only the
  backend sample app was ever built — now called out explicitly as a
  **Future enhancement** in the README instead of implied by an empty
  directory). Also corrected the README's repository-layout listing and
  several other places that had drifted into claiming either more or
  less than was actually true — see the README's own **Limitations**
  section for the current, honest list.

## Known, deliberate simplifications

- **Kubernetes target is local `kind`, not AWS EKS.** Provisioning is real
  (real `terraform apply`, real namespaces/pods), just against a local
  cluster. AWS Terraform modules exist for the cloud path, validated and
  plan-checked, but `apply` is never run against them in this project —
  a deliberate policy, not a constraint of missing credentials.
- **GitHub webhooks are triggered by a local simulator script**, since this
  sandbox has no public URL for github.com to call. The webhook handler
  itself — signature verification, idempotency, PR state handling — is the
  real code path; only the transport is simulated for local dev.
- **Cost figures are `estimated`/`simulated`**, never real cloud billing —
  there is no billing API integration.
