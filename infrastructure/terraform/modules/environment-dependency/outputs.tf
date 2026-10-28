output "service_name" {
  value = kubernetes_service_v1.dependency.metadata[0].name
}
