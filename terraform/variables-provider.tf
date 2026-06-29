variable "region" {
  description = "AWS Region"
  type        = string
  default     = "ca-central-1"
}

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

variable "ecr_repository_prefix" {
  description = "Prefix for ECR repository names"
  type        = string
  default     = "if"
}