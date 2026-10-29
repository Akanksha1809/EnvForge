# Cloud deployment (AWS) — written, not executed here

`infrastructure/terraform/modules/aws-platform` is real, reviewable
Terraform covering a VPC, an EKS cluster with one managed node group, RDS
(Postgres), ElastiCache (Redis), three ECR repositories, and the IAM/IRSA
role the AWS Load Balancer Controller needs. `terraform init
-backend=false && terraform validate` passes against it and its
`environments/aws` root module — confirmed when it was written — which
means the HCL is syntactically valid and every reference resolves.

**Nothing here has been applied, and `terraform apply` is deliberately
never run against this module in this project** — the project's spec
explicitly prohibits claiming cloud infrastructure was provisioned when it
wasn't, and this is enforced as a policy decision, not merely because
credentials happen to be unavailable: `terraform plan` against
`environments/aws` was run once, while writing this module, purely to
confirm the plan resolves without error, and it reached a point of making
one live, read-only AWS API call (`DescribeAvailabilityZones`) before
stopping — meaning *some* AWS credential path is reachable from whatever
sandbox that was run in. That changes nothing about the policy: this
module's resources were never created, `apply` was never run, and it
won't be without a human explicitly choosing to run it against their own
AWS account. See `docs/adr/0001-local-kind-for-provisioning.md` for why
local `kind` is the only provisioning target actually exercised in this
build, and `infrastructure/terraform/modules/aws-platform/README.md` for
a file-by-file breakdown of the module.

## What `terraform apply` would create, and roughly what it costs

Default `environments/aws` variables (`db.t4g.micro` RDS, `cache.t4g.micro`
Redis, 2× `t3.medium` EKS nodes, a single shared NAT gateway), `us-east-1`
on-demand pricing, left running continuously for a month — **none of this
is covered by AWS Free Tier**:

| Resource | Approx. monthly cost |
|---|---|
| EKS control plane | ~$73 (`$0.10/hr`) |
| 2× `t3.medium` EKS worker nodes | ~$60 |
| 1× NAT gateway (base price, excl. data processing) | ~$33 |
| RDS `db.t4g.micro` (single-AZ, 20GB gp3) | ~$15 |
| ElastiCache `cache.t4g.micro` (single node) | ~$12 |
| ECR storage (3 repos, a handful of images) | ~$1 |
| ALB(s) provisioned on-demand by the Load Balancer Controller, per Ingress | ~$16 each + data |
| **Total (idle platform, no ALBs yet)** | **~$195/month**, before any PR preview environments or data transfer |

Every additional EnvForge preview environment adds its own namespace's
pod/ingress costs on top (comparable to the per-environment resource
requests already enforced locally via `ResourceQuota` — see
`infrastructure/terraform/modules/environment-namespace`), plus one ALB
per unique ingress host if the Load Balancer Controller doesn't share one.

## Prerequisites before anyone applies this for real

1. An AWS account with billing alerts configured, and credentials with
   (at minimum) `AdministratorAccess` for the initial apply — the module
   itself creates scoped IAM roles for the workloads that run after it
   (EKS nodes, the Load Balancer Controller), but the *applying* identity
   still needs broad create permissions for first-time setup.
2. A remote Terraform state backend (S3 + DynamoDB lock table) — the
   module currently has no `backend` block, matching `environments/local`,
   since neither target has been applied anywhere that needs shared
   state. Add one before a second person ever runs `apply` against this.
3. After `apply`: install the AWS Load Balancer Controller via its Helm
   chart, passing `module.platform.lb_controller_role_arn` as the
   `eks.amazonaws.com/role-arn` annotation on its service account — the
   Terraform here provisions the IAM identity, not the controller itself
   (same division of labor as `ingress-nginx` locally).
4. Point `app/services/provisioning.py`'s kubeconfig handling at the new
   cluster (`aws eks update-kubeconfig`) instead of `kind`'s
   `host.docker.internal` rewrite — that rewrite is specifically a
   workaround for reaching a local cluster from inside a Docker container
   and doesn't apply to a real EKS endpoint.

## Teardown procedure

1. Delete every EnvForge-managed namespace first (`kubectl get ns -l
   envforge.io/managed=true`), or run the platform's own cleanup engine
   to drain them — Terraform doesn't know about per-environment
   Kubernetes objects applied by `environment-namespace`/`environment-app`
   against this cluster; they'd otherwise be orphaned the same way an
   orphaned local `kind` namespace is (see Phase 5's cleanup engine).
2. `terraform destroy` from `environments/aws`, in the default dependency
   order Terraform computes (it will tear down the node group and cluster
   before the VPC, RDS before its subnet group, etc.).
3. Manually verify and remove anything Terraform doesn't own: ALB-managed
   CloudWatch log groups, any S3 state bucket, and EBS snapshots RDS
   leaves behind if `skip_final_snapshot` was ever changed to `false` for
   a real deployment.
4. Delete the IAM OIDC provider and the Secrets Manager secret's
   underlying recovery window if you need it gone immediately — the
   default `aws_secretsmanager_secret` recovery window otherwise keeps it
   (and its cost) around for up to 30 days after `destroy`.

## IAM scope already built in

Both the EKS node group and the AWS Load Balancer Controller get
purpose-scoped IAM roles — `AmazonEKSWorkerNodePolicy` +
`AmazonEKS_CNI_Policy` + ECR read-only for nodes, and the Load Balancer
Controller's own published policy (`policies/aws-load-balancer-controller.json`)
for IRSA — rather than a single broad role shared by everything in the
cluster. There is no separate "EnvForge provisioning identity" IAM role
in this module: in the cloud path, the same Celery worker that calls
Terraform/kubectl against `kind` locally would call them against this
EKS cluster instead, authenticating as whatever principal `aws eks
update-kubeconfig` configures — scoping *that* identity down from
cluster-admin to "can manage `envforge.io/managed=true` namespaces only"
is real follow-up work, not yet done, and is called out here rather than
left silently assumed.

Until an AWS account and credentials are available and someone explicitly
chooses to run `terraform apply` against `environments/aws`, this remains
a paper design, validated for correctness but never deployed.
