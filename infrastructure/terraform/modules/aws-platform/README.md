# AWS platform module

Real, reviewable Terraform for the cloud path EnvForge's Kubernetes
provisioning targets *could* run against — a VPC, an EKS cluster with one
managed node group, RDS Postgres, ElastiCache Redis, three ECR
repositories, and the IAM/IRSA wiring the AWS Load Balancer Controller
needs. **`terraform apply` has never been run against this module, and
never will be as part of this project** — that's a deliberate policy
decision (see `docs/cloud-deployment.md` for why), independent of whether
any particular sandbox happens to have AWS credentials reachable.
Everything below is what *would* happen if someone chose to apply it
against their own AWS account.

See `docs/cloud-deployment.md` for the cost estimate, the manual steps
still required after `apply` (installing `ingress-nginx`'s cloud
equivalent — the AWS Load Balancer Controller Helm chart — and pointing
`app/services/provisioning.py`'s kubeconfig handling at the new cluster
instead of `kind`), and the teardown procedure. See
`docs/adr/0001-local-kind-for-provisioning.md` for why the local `kind`
path was chosen as the one this project actually demonstrates.

## What's here

| File | Provisions |
|---|---|
| `vpc.tf` | VPC, public+private subnets across 2 AZs, IGW, NAT gateway(s), route tables |
| `eks.tf` | EKS cluster, one managed node group, cluster/node IAM roles, OIDC provider + IRSA role for the AWS Load Balancer Controller |
| `rds.tf` | RDS Postgres (private subnets only), master credentials in Secrets Manager |
| `elasticache.tf` | ElastiCache Redis replication group (private subnets only) |
| `ecr.tf` | ECR repositories for `envforge-api`/`envforge-worker`/`envforge-frontend`, immutable tags, scan-on-push |
| `policies/aws-load-balancer-controller.json` | The published IAM policy the AWS Load Balancer Controller's IRSA role needs |

`environments/aws/` wires this module up as a standalone root module with
sane defaults (see its `variables.tf`) — the AWS equivalent of
`environments/local/`.

## Verified without applying

`terraform init -backend=false && terraform validate` passes against this
module and its `environments/aws` root (checked when this module was
written). That confirms the HCL is syntactically and type-correct and
every resource/attribute reference resolves.

`terraform plan` was also run once, for review, and completed with "47 to
add, 0 to change, 0 to destroy" and no errors — including one live,
read-only AWS API call (`DescribeAvailabilityZones`) that the `aws`
provider needs to resolve `data.aws_availability_zones.available`. That
call didn't create, modify, or cost anything, and nothing further was
done with that plan (no `-out`, no `apply`) — but it does mean the plan
itself is not just syntactically valid, it's a plan AWS's API agreed
would work, for whatever credentials were reachable in that run. It does
**not** mean a real `apply` has been attempted, would be attempted, or is
something this project does — see `docs/cloud-deployment.md` for why
`apply` is a deliberate policy line this project doesn't cross, regardless
of credential availability.

## Known gaps versus a production deployment

- Single NAT gateway by default (`var.single_nat_gateway = true`) — one
  AZ's outage takes down outbound internet for the whole private subnet
  tier. Flip to `false` for per-AZ NAT gateways.
- `multi_az = false` on the RDS instance by default — no standby replica.
- No automated backups/snapshots lifecycle beyond RDS's own 7-day retention.
- No WAF, no Shield Advanced, no cross-region DR.
- The AWS Load Balancer Controller and cluster-autoscaler are Helm
  installs, not Terraform resources (same division of labor as
  `ingress-nginx` in the local path) — this module provisions the IAM role
  they need, not the controllers themselves.
