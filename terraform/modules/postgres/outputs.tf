output "host" {
  value = "${var.cluster_name}-rw.${var.namespace}.svc.cluster.local"
}
output "port" {
  value = 5432
}
output "database" {
  value = var.database
}
output "username" {
  value = var.username
}
output "password" {
  value     = local.database_password_effective
  sensitive = true
}
output "cluster_name" {
  value = var.cluster_name
}
