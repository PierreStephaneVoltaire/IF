variable "tools_path" {
  description = "Path to external tools directory (mounted volume)"
  type        = string
  default     = "/app/tools"
}

variable "specialists_path" {
  description = "Path to specialists directory (mounted volume)"
  type        = string
  default     = "/app/specialists"
}

variable "models_path" {
  description = "Path to models directory (mounted volume)"
  type        = string
  default     = "/app/models"
}

variable "scripts_path" {
  description = "Path to scripts directory (mounted volume)"
  type        = string
  default     = "/app/scripts"
}

variable "skills_path" {
  description = "Path to AgentSkills directory (mounted volume)"
  type        = string
  default     = "/app/skills"
}

variable "tools_host_path" {
  description = "Host path to tools directory for hostPath volume"
  type        = string
}

variable "specialists_host_path" {
  description = "Host path to specialists directory for hostPath volume"
  type        = string
}

variable "models_host_path" {
  description = "Host path to models directory for hostPath volume"
  type        = string
}

variable "scripts_host_path" {
  description = "Host path to scripts directory for hostPath volume"
  type        = string
}

variable "skills_host_path" {
  description = "Host path to AgentSkills directory for hostPath volume"
  type        = string
}