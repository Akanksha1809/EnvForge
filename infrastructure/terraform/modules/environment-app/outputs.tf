output "service_name" {
  value = kubernetes_service_v1.app.metadata[0].name
}

output "deployment_name" {
  value = kubernetes_deployment_v1.app.metadata[0].name
}

output "preview_url" {
  value = (
    var.ingress_host == null ? null :
    var.ingress_port == 80 ? "http://${var.ingress_host}" :
    "http://${var.ingress_host}:${var.ingress_port}"
  )
}
