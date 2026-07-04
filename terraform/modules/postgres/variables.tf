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
variable "cluster_name" {
  type    = string
  default = "postgres"
}
variable "instances" {
  type    = number
  default = 2
}
variable "storage_size" {
  type    = string
  default = "10Gi"
}
variable "database" {
  type    = string
  default = "authentik"
}
variable "username" {
  type    = string
  default = "authentik"
}
variable "cnpg_chart_version" {
  type    = string
  default = "0.29.0"
}
