output "server_service_name" {
  value = "authentik-server"
}
output "server_service_port" {
  value = 80
}
output "namespace" {
  value = var.namespace
}
output "terraform_token_secret_name" {
  value = kubernetes_secret.authentik_terraform_token.metadata[0].name
}
