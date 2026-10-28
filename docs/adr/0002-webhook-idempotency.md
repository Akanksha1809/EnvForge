# ADR 0002: Two-layer idempotency for GitHub webhooks

## Status
Accepted (Phase 4).

## Context
GitHub redelivers a webhook on timeout or a non-2xx response, and in
practice duplicate/out-of-order delivery is routine (e.g. `synchronize`
racing `opened` for a PR created and immediately pushed to). The spec
requires "idempotent webhook processing" and "avoid creating duplicate
environments."

## Decision
Two independent layers, neither sufficient alone:

1. **Transport-level dedupe**: `WebhookDelivery` keyed by GitHub's own
   `X-GitHub-Delivery` id. A redelivered *identical* webhook is a no-op.
   This alone doesn't help if GitHub (or a flaky network) sends
   `opened` and then a near-duplicate `synchronize` with a new delivery
   id before our environment exists yet.
2. **Domain-level dedupe**: `get_active_environment_for_pr` looks up by
   (application, pr_number, non-terminal state) before deciding whether
   to create or reuse. `opened`, a redelivered `opened`, and an
   out-of-order `synchronize` all converge on the same Environment row.

## Consequences
- A PR can only ever have one non-terminal Environment, regardless of
  event ordering or redelivery — verified in
  `tests/integration/test_github_webhook_api.py`.
- A "new commit" redeploy reuses the environment's existing Terraform
  workspace/state (real idempotency — `terraform apply` reconciles
  rather than re-creating), which is also why the lifecycle table gained
  `READY -> PROVISIONING` and `FAILED -> PROVISIONING` edges (ADR
  context, not a separate decision): a redeploy is a real state
  transition, not a special case bolted outside the state machine.
- Concurrent redeploys are deliberately *not* fully solved: if a
  provisioning run is already in flight, a new webhook updates the
  tracked commit SHA but does not dispatch a second `terraform apply`
  against the same (unlocked, local) state file. This is a documented
  simplification, not silently dropped work — see `docs/roadmap.md`.
