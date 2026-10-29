# Cloud provisioning target: real AWS (VPC/EKS/RDS/ElastiCache/ECR), via
# infrastructure/terraform/modules/aws-platform. See ../local/ for the
# kind-cluster target this project actually applies, and
# docs/cloud-deployment.md for why this one never is in this environment.
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }
}

provider "aws" {
  region = var.aws_region
}
