variable "namespace" {
  type = string
}

variable "name" {
  description = "Dependency name, e.g. \"postgres\" or \"redis\" — becomes the in-cluster DNS name other containers in the namespace use to reach it."
  type        = string
}

variable "image" {
  type = string
}

variable "port" {
  type = number
}

variable "env_vars" {
  type    = map(string)
  default = {}
}

variable "cpu_request" {
  type    = string
  default = "50m"
}

variable "memory_request" {
  type    = string
  default = "64Mi"
}

variable "cpu_limit" {
  type    = string
  default = "250m"
}

variable "memory_limit" {
  type    = string
  default = "256Mi"
}
