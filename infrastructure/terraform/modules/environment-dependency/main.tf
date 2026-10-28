# A "temporary dependency" (Postgres/Redis/etc for a preview environment):
# a plain Deployment with no PersistentVolumeClaim. Ephemeral by design —
# when the environment is destroyed, its data goes with it, which is the
# correct behavior for a short-lived PR preview.
resource "kubernetes_deployment_v1" "dependency" {
  metadata {
    name      = var.name
    namespace = var.namespace
    labels    = { app = var.name, "envforge.io/dependency" = "true" }
  }

  spec {
    replicas = 1
    selector {
      match_labels = { app = var.name }
    }
    template {
      metadata {
        labels = { app = var.name }
      }
      spec {
        container {
          name  = var.name
          image = var.image

          dynamic "env" {
            for_each = var.env_vars
            content {
              name  = env.key
              value = env.value
            }
          }

          port {
            container_port = var.port
          }

          resources {
            requests = {
              cpu    = var.cpu_request
              memory = var.memory_request
            }
            limits = {
              cpu    = var.cpu_limit
              memory = var.memory_limit
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "dependency" {
  metadata {
    name      = var.name
    namespace = var.namespace
  }
  spec {
    selector = { app = var.name }
    port {
      port        = var.port
      target_port = var.port
    }
  }
}
