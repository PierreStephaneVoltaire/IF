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

# ─── Bootstrap (first-startup only) ──────────────────────────────────────────
# Read by the authentik worker on first startup to create the akadmin user and
# an API token. The token is then used by the authentik-provider stack.
variable "bootstrap_email" {
  description = "Email for the akadmin user created on first startup."
  type        = string
}
variable "bootstrap_password" {
  description = "Password for the akadmin user created on first startup."
  type        = string
  sensitive   = true
}
variable "bootstrap_token" {
  description = "API token created for akadmin on first startup. Used by the authentik-provider stack."
  type        = string
  sensitive   = true
}
