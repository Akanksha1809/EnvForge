variable "namespace_name" {
  description = "Kubernetes namespace for this environment. One namespace per environment is the isolation boundary."
  type        = string
}

variable "environment_id" {
  description = "EnvForge environment UUID, stamped as a label for traceability back to the platform."
  type        = string
}

variable "application_slug" {
  type = string
}

variable "team_slug" {
  type = string
}

variable "cpu_request_limit" {
  description = "Total CPU the namespace's ResourceQuota allows, across all pods."
  type        = string
  default     = "2"
}

variable "memory_request_limit" {
  description = "Total memory the namespace's ResourceQuota allows, across all pods."
  type        = string
  default     = "2Gi"
}

variable "max_pods" {
  type    = number
  default = 10
}
