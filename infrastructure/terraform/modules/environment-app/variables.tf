variable "namespace" {
  type = string
}

variable "app_name" {
  description = "Used for resource names and the k8s app label."
  type        = string
}

variable "image" {
  type = string
}

variable "container_port" {
  type    = number
  default = 8000
}

variable "replicas" {
  type    = number
  default = 1
}

variable "env_vars" {
  description = "Plain (non-secret) environment variables, stored in a ConfigMap."
  type        = map(string)
  default     = {}
}

variable "secret_env_vars" {
  description = "Secret environment variables. Stored in a Kubernetes Secret and referenced by name only — Terraform state is the only place the value is held outside the cluster, and this module never outputs it."
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "cpu_request" {
  type    = string
  default = "100m"
}

variable "memory_request" {
  type    = string
  default = "128Mi"
}

variable "cpu_limit" {
  type    = string
  default = "500m"
}

variable "memory_limit" {
  type    = string
  default = "512Mi"
}

variable "health_check_path" {
  type    = string
  default = "/health"
}

variable "ingress_host" {
  description = "If set, an Ingress is created routing this host to the app's Service."
  type        = string
  default     = null
}

variable "ingress_class_name" {
  type    = string
  default = "nginx"
}

variable "ingress_port" {
  description = "Host port the ingress controller is actually reachable on — 80 for a real LoadBalancer/cloud setup, but kind maps it to an arbitrary host port (see infrastructure/kubernetes/kind-cluster.yaml), so the preview_url output needs to know it to be a URL that actually works."
  type        = number
  default     = 80
}
