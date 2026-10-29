output "vpc_id" {
  value = aws_vpc.this.id
}

output "eks_cluster_name" {
  value = aws_eks_cluster.this.name
}

output "eks_cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}

output "eks_cluster_certificate_authority" {
  value     = aws_eks_cluster.this.certificate_authority[0].data
  sensitive = true
}

output "eks_oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.this.arn
}

output "lb_controller_role_arn" {
  description = "Pass as the eks.amazonaws.com/role-arn annotation on the aws-load-balancer-controller service account."
  value       = aws_iam_role.lb_controller.arn
}

output "rds_endpoint" {
  value = aws_db_instance.this.address
}

output "rds_secret_arn" {
  description = "Secrets Manager ARN holding the RDS master credentials — fetch at deploy time, never commit them."
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "redis_primary_endpoint" {
  value = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "ecr_repository_urls" {
  value = { for name, repo in aws_ecr_repository.this : name => repo.repository_url }
}
