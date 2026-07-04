variable "kubeconfig_path" {
  type    = string
  default = "~/.kube/config"
}
variable "kubeconfig_context" {
  type    = string
  default = "default"
}
variable "namespace" {
  type    = string
  default = "if-portals"
}
variable "chart_version" {
  type    = string
  default = "2026.5.3"
}
variable "postgresql_host" {
  type = string
}
variable "postgresql_port" {
  type    = number
  default = 5432
}
variable "postgresql_database" {
  type    = string
  default = "authentik"
}
variable "postgresql_username" {
  type    = string
  default = "authentik"
}
variable "postgresql_password" {
  type      = string
  sensitive = true
}
variable "server_replicas" {
  type    = number
  default = 1
}
variable "worker_replicas" {
  type    = number
  default = 1
}
