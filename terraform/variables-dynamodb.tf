variable "dynamodb_core_table" {
  description = "DynamoDB table for core directives"
  type        = string
  default     = "if-core"
}

variable "dynamodb_health_table" {
  description = "DynamoDB table for health program"
  type        = string
  default     = "if-health"
}

variable "dynamodb_templates_table" {
  description = "DynamoDB table for global powerlifting templates"
  type        = string
  default     = "if-health-templates"
}

variable "dynamodb_sessions_table" {
  description = "DynamoDB table for copied health sessions"
  type        = string
  default     = "if-sessions"
}

variable "dynamodb_analysis_cache_table" {
  description = "DynamoDB table for cached powerlifting analysis bundles"
  type        = string
  default     = "if-powerlifting-analysis-cache"
}

variable "dynamodb_finance_table" {
  description = "DynamoDB table for finance portal"
  type        = string
  default     = "if-finance"
}

variable "dynamodb_diary_entries_table" {
  description = "DynamoDB table for diary entries"
  type        = string
  default     = "if-diary-entries"
}

variable "dynamodb_diary_signals_table" {
  description = "DynamoDB table for diary signals"
  type        = string
  default     = "if-diary-signals"
}

variable "dynamodb_proposals_table" {
  description = "DynamoDB table for proposals portal"
  type        = string
  default     = "if-proposals"
}

variable "dynamodb_models_table" {
  description = "DynamoDB table for model metadata registry"
  type        = string
  default     = "if-models"
}

variable "dynamodb_execution_registry_table" {
  description = "DynamoDB table for channel execution registry"
  type        = string
  default     = "if-agent-execution-registry"
}

variable "dynamodb_webhooks_table" {
  description = "DynamoDB table for webhook/channel registration"
  type        = string
  default     = "if-webhooks"
}

variable "dynamodb_powerlifting_table" {
  description = "DynamoDB table for powerlifting app"
  type        = string
  default     = "powerlifting"
}

variable "dynamodb_user_table" {
  description = "DynamoDB table for user identity mappings and public profiles"
  type        = string
  default     = "if-user"
}

variable "dynamodb_powerlifting_master_competitions_table" {
  description = "DynamoDB table for the master powerlifting competition catalog (admin-owned, stream-enabled). Comps here are the source of truth that the master-sync Lambda fans out to per-user copies."
  type        = string
  default     = "if-powerlifting-master-competitions"
}

variable "dynamodb_powerlifting_user_competitions_table" {
  description = "DynamoDB table for per-user powerlifting competition copies (denormalized, Lambda-synced)."
  type        = string
  default     = "if-powerlifting-user-competitions"
}

variable "dynamodb_powerlifting_master_federations_table" {
  description = "DynamoDB table for the master powerlifting federation catalog (admin-owned, stream-enabled)."
  type        = string
  default     = "if-powerlifting-master-federations"
}

variable "dynamodb_powerlifting_user_federations_table" {
  description = "DynamoDB table for per-user powerlifting federation copies (denormalized, Lambda-synced)."
  type        = string
  default     = "if-powerlifting-user-federations"
}

variable "dynamodb_powerlifting_goals_table" {
  description = "DynamoDB table for per-user powerlifting goals (one row per goal, no program version)."
  type        = string
  default     = "if-powerlifting-goals"
}