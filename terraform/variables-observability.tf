variable "loki_storage_gb" {
  description = "Storage size for Loki log data (GB)"
  type        = number
  default     = 10
}

variable "prometheus_storage_gb" {
  description = "Storage size for Prometheus metrics (GB)"
  type        = number
  default     = 10
}

variable "grafana_storage_gb" {
  description = "Storage size for Grafana dashboards (GB)"
  type        = number
  default     = 2
}

variable "log_retention_days" {
  description = "Days to retain logs in Loki"
  type        = number
  default     = 7
}

variable "metrics_retention_days" {
  description = "Days to retain metrics in Prometheus"
  type        = number
  default     = 15
}

variable "grafana_admin_password" {
  description = "Grafana admin user password"
  type        = string
  sensitive   = true
  default     = "admin"
}

variable "monitoring_zone" {
  description = "Cloudflare zone (apex domain) where the monitoring subdomain lives (e.g. if-prototype.xyz)"
  type        = string
  default     = "if-prototype.xyz"
}

variable "monitoring_subdomain" {
  description = "Subdomain prefix for the Grafana log viewer (e.g. logs → logs.if-prototype.xyz)"
  type        = string
  default     = "logs"
}