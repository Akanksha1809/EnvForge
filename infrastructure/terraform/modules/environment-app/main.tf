# Configuration isolation: each environment's non-secret config lives in
# its own ConfigMap inside its own namespace — nothing is shared globally.
resource "kubernetes_config_map_v1" "env" {
  metadata {
    name      = "${var.app_name}-config"
    namespace = var.namespace
  }
  data = var.env_vars
}

# Secret isolation: secret values are only ever referenced by name
# (secretRef) in the Deployment spec below, never interpolated into a
# ConfigMap, log line, or Terraform output.
resource "kubernetes_secret_v1" "env" {
  metadata {
    name      = "${var.app_name}-secrets"
    namespace = var.namespace
  }
  data = var.secret_env_vars
  type = "Opaque"
}

resource "kubernetes_deployment_v1" "app" {
  metadata {
    name      = var.app_name
    namespace = var.namespace
    labels    = { app = var.app_name }
  }

  spec {
    replicas = var.replicas

    selector {
      match_labels = { app = var.app_name }
    }

    template {
      metadata {
        labels = { app = var.app_name }
      }

      spec {
        container {
          name  = var.app_name
          image = var.image

          port {
            container_port = var.container_port
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map_v1.env.metadata[0].name
            }
          }
          env_from {
            secret_ref {
              name = kubernetes_secret_v1.env.metadata[0].name
            }
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

          readiness_probe {
            http_get {
              path = var.health_check_path
              port = var.container_port
            }
            initial_delay_seconds = 3
            period_seconds        = 5
            failure_threshold     = 6
          }

          liveness_probe {
            http_get {
              path = var.health_check_path
              port = var.container_port
            }
            initial_delay_seconds = 10
            period_seconds        = 15
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "app" {
  metadata {
    name      = var.app_name
    namespace = var.namespace
  }
  spec {
    selector = { app = var.app_name }
    port {
      port        = 80
      target_port = var.container_port
    }
  }
}

resource "kubernetes_ingress_v1" "app" {
  count = var.ingress_host == null ? 0 : 1

  metadata {
    name      = var.app_name
    namespace = var.namespace
  }
  spec {
    ingress_class_name = var.ingress_class_name
    rule {
      host = var.ingress_host
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = kubernetes_service_v1.app.metadata[0].name
              port {
                number = 80
              }
            }
          }
        }
      }
    }
  }
}
