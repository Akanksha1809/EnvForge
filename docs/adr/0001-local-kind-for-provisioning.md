# ADR 0001: Provision against a local `kind` cluster, not a mocked backend

## Status
Accepted (Phase 3).

## Context
The spec requires real infrastructure automation — Kubernetes namespaces,
deployments, services, ingress, network policies — provisioned by
Terraform, and explicitly forbids faking integrations. This project runs
in an environment with no AWS account or cloud credentials.

## Decision
Target a real local `kind` (Kubernetes-in-Docker) cluster with
`ingress-nginx` installed, using the real `hashicorp/kubernetes` Terraform
provider and real `kubectl` calls for health checks. AWS/EKS Terraform
modules are written for the cloud path (Phase 8/9) but never executed
here.

## Consequences
- Every resource EnvForge "provisions" locally is a real Kubernetes object
  you can `kubectl get` — not a database row pretending to be
  infrastructure.
- The Celery worker needs network access to the kind cluster's API
  server. Running the worker as a Docker container introduces a real
  wrinkle: the host's kubeconfig records the API server as
  `127.0.0.1:<port>`, which inside a container is the container itself.
  Solved by rewriting the kubeconfig to use `host.docker.internal` when
  `RUNNING_IN_DOCKER=true` (see `app/services/provisioning.py`) — or by
  running the worker directly on the host (`make worker-host`), which
  needs no such rewrite since it reaches `kind` exactly like a developer's
  own `kubectl` would.
- A reviewer can reproduce every claim in this project's demo without any
  cloud account: `make kind-up && make kind-ingress && make
  build-sample-backend && make dev`.
- The tradeoff: this cannot demonstrate real cloud networking (ALBs, real
  DNS, VPC isolation) or cloud-specific IAM. Those are addressed on paper
  by the AWS Terraform modules and `docs/cloud-deployment.md`, explicitly
  labeled as written-but-not-executed.
