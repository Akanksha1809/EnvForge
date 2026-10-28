variable "kube_context" {
  type    = string
  default = "kind-envforge"
}

variable "kubeconfig_path" {
  type    = string
  default = "~/.kube/config"
}

variable "environment_id" {
  type = string
}

variable "namespace_name" {
  type = string
}

variable "application_slug" {
  type = string
}

variable "team_slug" {
  type = string
}

variable "app_name" {
  type = string
}

variable "app_image" {
  type = string
}

variable "app_port" {
  type    = number
  default = 8000
}

variable "app_replicas" {
  type    = number
  default = 1
}

variable "app_env_vars" {
  type    = map(string)
  default = {}
}

variable "app_secret_env_vars" {
  type      = map(string)
  default   = {}
  sensitive = true
}

variable "app_resources" {
  type = object({
    cpu_request    = string
    memory_request = string
    cpu_limit      = string
    memory_limit   = string
  })
  default = {
    cpu_request    = "100m"
    memory_request = "128Mi"
    cpu_limit      = "500m"
    memory_limit   = "512Mi"
  }
}

variable "health_check_path" {
  type    = string
  default = "/health"
}

variable "ingress_host" {
  type    = string
  default = null
}

variable "ingress_port" {
  type    = number
  default = 80
}

variable "namespace_quota" {
  type = object({
    cpu    = string
    memory = string
    pods   = number
  })
  default = {
    cpu    = "2"
    memory = "2Gi"
    pods   = 10
  }
}

variable "dependencies" {
  description = "Temporary in-namespace dependencies (e.g. postgres, redis)."
  type = list(object({
    name     = string
    image    = string
    port     = number
    env_vars = map(string)
  }))
  default = []
}
