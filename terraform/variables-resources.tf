variable "portal_memory_mb" {
  description = "Memory limit for portal backends (MB)"
  type        = number
  default     = 1024
}

variable "portal_cpu_millicores" {
  description = "CPU limit for portal backends (millicores)"
  type        = number
  default     = 500
}

variable "api_memory_mb" {
  description = "Memory limit for main API (MB)"
  type        = number
  default     = 5120
}

variable "api_memory_request_mb" {
  description = "Memory request for main API (MB) — used for scheduling; should reflect steady-state usage after dataset warm-up"
  type        = number
  default     = 2048
}

variable "api_cpu_request_millicores" {
  description = "CPU request for main API (millicores)"
  type        = number
  default     = 2000
}

variable "api_cpu_millicores" {
  description = "CPU limit for main API (millicores)"
  type        = number
  default     = 1000
}

variable "frontend_memory_mb" {
  description = "Memory limit for portal frontends (MB)"
  type        = number
  default     = 256
}

variable "frontend_cpu_millicores" {
  description = "CPU limit for portal frontends (millicores)"
  type        = number
  default     = 100
}

variable "aws_credentials_host_path" {
  description = "Path to AWS credentials directory on the k3s node (mounted into pods)"
  type        = string
  default     = "/root/.aws"
}