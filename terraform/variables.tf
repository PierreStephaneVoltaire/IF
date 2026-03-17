variable "region" {
  description = "AWS Region"
  type        = string
  default     = "ca-central-1"
}

variable "aws_access_key" {
  description = "AWS Access Key ID"
  type        = string
  sensitive   = true
}

variable "aws_secret_key" {
  description = "AWS Secret Access Key"
  type        = string
  sensitive   = true
}

# k3s cluster configuration
variable "kubeconfig_path" {
  description = "Path to kubeconfig file for k3s cluster"
  type        = string
  default     = "~/.kube/config"
}

variable "kubeconfig_context" {
  description = "Kubernetes context for k3s cluster"
  type        = string
  default     = "default"
}

# ECR repository prefix
variable "ecr_repository_prefix" {
  description = "Prefix for ECR repository names"
  type        = string
  default     = "if"
}

# Resource limits - Portals
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

# Resource limits - Main API
variable "api_memory_mb" {
  description = "Memory limit for main API (MB)"
  type        = number
  default     = 2048
}

variable "api_cpu_millicores" {
  description = "CPU limit for main API (millicores)"
  type        = number
  default     = 1000
}

# Resource limits - Frontends
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

