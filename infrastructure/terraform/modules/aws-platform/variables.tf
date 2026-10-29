# Variables for the AWS cloud platform module. Written to be real,
# reviewable Terraform (see README.md for why it is never applied in this
# environment) — defaults favor the cheapest configuration that still
# demonstrates the real pattern (single NAT gateway, small instance
# classes), not a production-sized deployment.

variable "project_name" {
  description = "Prefix applied to every resource name/tag, e.g. \"envforge\"."
  type        = string
  default     = "envforge"
}

variable "environment_name" {
  description = "Deployment environment label, e.g. \"staging\" or \"production\". Distinct from an EnvForge preview `Environment` row — this is the cloud platform itself, provisioned once, that EnvForge's own per-PR namespaces then live inside."
  type        = string
  default     = "staging"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "availability_zone_count" {
  description = "Number of AZs to spread public/private subnets across."
  type        = number
  default     = 2
}

variable "single_nat_gateway" {
  description = "Use one shared NAT gateway for all private subnets instead of one per AZ. Cheaper, less available — the right tradeoff for a non-production demo platform; set false for a real production deployment."
  type        = bool
  default     = true
}

variable "kubernetes_version" {
  type    = string
  default = "1.31"
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.medium"]
}

variable "node_group_min_size" {
  type    = number
  default = 1
}

variable "node_group_max_size" {
  type    = number
  default = 4
}

variable "node_group_desired_size" {
  type    = number
  default = 2
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_engine_version" {
  type    = string
  default = "16.4"
}

variable "db_allocated_storage_gb" {
  type    = number
  default = 20
}

variable "db_name" {
  type    = string
  default = "envforge"
}

variable "db_username" {
  type    = string
  default = "envforge"
}

variable "db_multi_az" {
  description = "Run a standby replica in a second AZ. Off by default to keep the paper cost estimate honest for a demo deployment."
  type        = bool
  default     = false
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "redis_num_cache_clusters" {
  type    = number
  default = 1
}

variable "ecr_repository_names" {
  description = "Container image repositories to create, one per EnvForge service image."
  type        = list(string)
  default     = ["envforge-api", "envforge-worker", "envforge-frontend"]
}

variable "ecr_image_tag_mutability" {
  type    = string
  default = "IMMUTABLE"
}

variable "tags" {
  description = "Extra tags merged onto every resource this module creates."
  type        = map(string)
  default     = {}
}
