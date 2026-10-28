module "namespace" {
  source = "../../modules/environment-namespace"

  namespace_name       = var.namespace_name
  environment_id       = var.environment_id
  application_slug     = var.application_slug
  team_slug            = var.team_slug
  cpu_request_limit    = var.namespace_quota.cpu
  memory_request_limit = var.namespace_quota.memory
  max_pods             = var.namespace_quota.pods
}

module "dependencies" {
  source   = "../../modules/environment-dependency"
  for_each = { for dep in var.dependencies : dep.name => dep }

  namespace = module.namespace.namespace_name
  name      = each.value.name
  image     = each.value.image
  port      = each.value.port
  env_vars  = each.value.env_vars
}

module "app" {
  source = "../../modules/environment-app"

  namespace         = module.namespace.namespace_name
  app_name          = var.app_name
  image             = var.app_image
  container_port    = var.app_port
  replicas          = var.app_replicas
  env_vars          = var.app_env_vars
  secret_env_vars   = var.app_secret_env_vars
  cpu_request       = var.app_resources.cpu_request
  memory_request    = var.app_resources.memory_request
  cpu_limit         = var.app_resources.cpu_limit
  memory_limit      = var.app_resources.memory_limit
  health_check_path = var.health_check_path
  ingress_host      = var.ingress_host
  ingress_port      = var.ingress_port

  depends_on = [module.dependencies]
}
