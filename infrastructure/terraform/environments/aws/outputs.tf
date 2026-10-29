output "eks_cluster_name" {
  value = module.platform.eks_cluster_name
}

output "eks_cluster_endpoint" {
  value = module.platform.eks_cluster_endpoint
}

output "rds_endpoint" {
  value = module.platform.rds_endpoint
}

output "redis_primary_endpoint" {
  value = module.platform.redis_primary_endpoint
}

output "ecr_repository_urls" {
  value = module.platform.ecr_repository_urls
}

output "lb_controller_role_arn" {
  value = module.platform.lb_controller_role_arn
}
