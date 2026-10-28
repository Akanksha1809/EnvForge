# Cloud deployment (AWS) — planned, not executed here

This document will cover deploying EnvForge's own platform (not the
ephemeral environments it provisions) to AWS, once the Phase 8 Terraform
modules (`infrastructure/terraform/modules/aws-platform`) are written:
VPC, EKS, RDS (Postgres), ElastiCache (Redis), ECR, and an Application
Load Balancer.

**Nothing here has been applied.** This environment has no AWS account or
credentials, and the project's spec explicitly prohibits claiming cloud
infrastructure was provisioned when it wasn't. See
`docs/adr/0001-local-kind-for-provisioning.md` for why local `kind` is the
only provisioning target actually exercised in this build.

Before anyone applies the AWS modules for real, this document will need:

- **Cost estimate**: EKS control plane (~$0.10/hr), worker nodes, NAT
  gateway(s) (~$0.045/hr + data), an ALB, RDS and ElastiCache instance
  costs — none of which are covered by AWS Free Tier.
- **Teardown procedure**: `terraform destroy` order and a checklist for
  anything Terraform can't clean up on its own (e.g. ALB-managed
  CloudWatch log groups, S3 state buckets, EBS snapshots).
- **IAM**: least-privilege roles for the EKS node group and for
  EnvForge's own provisioning identity (it should be able to manage
  environment namespaces, not the whole cluster).

Until that's written and someone with an AWS account explicitly chooses
to apply it, this remains a paper design, not a deployed system.
