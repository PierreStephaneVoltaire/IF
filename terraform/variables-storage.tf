variable "log_level" {
  description = "Logging level"
  type        = string
  default     = "INFO"
}

variable "storage_class" {
  description = "Kubernetes storage class for persistent volumes"
  type        = string
  default     = "local-path"
}

variable "data_storage_gb" {
  description = "Storage size for main API data (GB)"
  type        = number
  default     = 10
}

variable "sandbox_storage_gb" {
  description = "Storage size for sandbox files (GB)"
  type        = number
  default     = 5
}

variable "conversations_storage_gb" {
  description = "Storage size for conversation persistence (GB)"
  type        = number
  default     = 5
}

variable "facts_storage_gb" {
  description = "Storage size for facts database (GB)"
  type        = number
  default     = 2
}