# Local provisioning target: a real local `kind` cluster. See
# ../aws/ for the (written-but-not-executed) cloud equivalent and
# docs/cloud-deployment.md for why it's never applied in this environment.
terraform {
  required_version = ">= 1.6"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.33"
    }
  }
}

provider "kubernetes" {
  config_path    = var.kubeconfig_path
  config_context = var.kube_context
}
