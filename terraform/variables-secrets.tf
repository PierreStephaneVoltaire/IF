variable "powerlifting_s3_bucket" {
  description = "S3 bucket with the OpenPowerlifting dataset (stats tools read from here)."
  type        = string
  default     = ""
}

variable "pl_internal_token" {
  description = "Internal API token gating powerlifting Fission function HTTP triggers (X-Internal-Token)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "openrouter_api_key" {
  description = "OpenRouter API key"
  type        = string
  sensitive   = true
}

variable "discord_token" {
  description = "Discord bot token"
  type        = string
  sensitive   = true
}

variable "alphavantage_api_key" {
  description = "Alpha Vantage API key for financial data"
  type        = string
  default     = ""
  sensitive   = true
}

variable "github_token" {
  description = "GitHub PAT for agent git operations (repo scope minimum)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "if_self_repo_url" {
  description = "Git URL (SSH or HTTPS) for the IF codebase. Injected into the agent pod as IF_SELF_REPO_URL for self-aware channel operations."
  type        = string
  default     = ""
}