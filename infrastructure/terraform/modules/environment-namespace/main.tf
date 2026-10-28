# Namespace isolation: one namespace per environment, labeled consistently
# so the cleanup engine (Phase 5) can find/orphan-detect EnvForge-owned
# namespaces by label selector rather than by name parsing.
resource "kubernetes_namespace_v1" "this" {
  metadata {
    name = var.namespace_name
    labels = {
      "envforge.io/managed"     = "true"
      "envforge.io/environment" = var.environment_id
      "envforge.io/application" = var.application_slug
      "envforge.io/team"        = var.team_slug
    }
  }
}

# Resource isolation: a hard ceiling on total compute the environment's
# namespace can consume, independent of any single pod's requests/limits.
resource "kubernetes_resource_quota_v1" "this" {
  metadata {
    name      = "${var.namespace_name}-quota"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    hard = {
      "requests.cpu"    = var.cpu_request_limit
      "requests.memory" = var.memory_request_limit
      "limits.cpu"      = var.cpu_request_limit
      "limits.memory"   = var.memory_request_limit
      "pods"            = tostring(var.max_pods)
    }
  }
}

# Every container in the namespace gets a sane default request/limit even
# if the application/template didn't specify one, so a misconfigured
# workload can't silently consume the whole quota.
resource "kubernetes_limit_range_v1" "this" {
  metadata {
    name      = "${var.namespace_name}-limits"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    limit {
      type = "Container"
      default = {
        cpu    = "250m"
        memory = "256Mi"
      }
      default_request = {
        cpu    = "100m"
        memory = "128Mi"
      }
    }
  }
}

# Network isolation: deny all ingress by default, then explicitly allow
# traffic from (a) other pods in the same namespace (app <-> its own
# dependencies) and (b) the ingress-nginx controller (so the preview URL
# can reach the app). Unrelated preview environments in other namespaces
# cannot reach this one.
resource "kubernetes_network_policy_v1" "default_deny" {
  metadata {
    name      = "default-deny-ingress"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress"]
  }
}

resource "kubernetes_network_policy_v1" "allow_intra_namespace_and_ingress" {
  metadata {
    name      = "allow-intra-namespace-and-ingress"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress"]

    ingress {
      from {
        pod_selector {}
      }
    }
    ingress {
      from {
        namespace_selector {
          match_labels = {
            "kubernetes.io/metadata.name" = "ingress-nginx"
          }
        }
      }
    }
  }
}
