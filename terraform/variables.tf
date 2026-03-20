variable "region" {
  description = "AWS Region"
  type        = string
  default     = "ca-central-1"
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

# =============================================================================
# API Keys (Secrets)
# =============================================================================

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

# =============================================================================
# DynamoDB Table Names
# =============================================================================

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

variable "dynamodb_powerlifting_table" {
  description = "DynamoDB table for powerlifting app"
  type        = string
  default     = "powerlifting"
}

# =============================================================================
# Tiering Configuration
# =============================================================================

variable "tier_upgrade_threshold" {
  description = "Fraction of context limit before tier upgrade"
  type        = number
  default     = 0.65
}

variable "tier_air_limit" {
  description = "Air tier context limit (tokens)"
  type        = number
  default     = 30000
}

variable "tier_standard_limit" {
  description = "Standard tier context limit (tokens)"
  type        = number
  default     = 120000
}

variable "tier_heavy_limit" {
  description = "Heavy tier context limit (tokens)"
  type        = number
  default     = 200000
}

variable "tier_air_preset" {
  description = "OpenRouter preset for air tier"
  type        = string
  default     = "@preset/air"
}

variable "tier_standard_preset" {
  description = "OpenRouter preset for standard tier"
  type        = string
  default     = "@preset/standard"
}

variable "tier_heavy_preset" {
  description = "OpenRouter preset for heavy tier"
  type        = string
  default     = "@preset/heavy"
}

# =============================================================================
# Specialist Configuration
# =============================================================================

variable "specialist_preset" {
  description = "Default preset for specialist subagents"
  type        = string
  default     = "@preset/standard"
}

variable "specialist_max_turns" {
  description = "Maximum turns per specialist"
  type        = number
  default     = 15
}

variable "thinking_preset" {
  description = "Preset for deep thinking subagent"
  type        = string
  default     = "@preset/general"
}

variable "thinking_max_turns" {
  description = "Maximum turns for deep thinking"
  type        = number
  default     = 20
}

# =============================================================================
# Model Configuration
# =============================================================================

variable "api_model_name" {
  description = "API model identifier for external clients"
  type        = string
  default     = "if-prototype"
}

variable "tokenizer_model" {
  description = "Tokenizer model for tiktoken"
  type        = string
  default     = "gpt-4"
}

variable "embedding_model" {
  description = "Embedding model for vector storage"
  type        = string
  default     = "all-MiniLM-L6-v2"
}

variable "suggestion_model" {
  description = "Model for OpenWebUI suggestions/titles"
  type        = string
  default     = "mistralai/mistral-nemo"
}

variable "directive_rewrite_model" {
  description = "Model for directive content rewriting"
  type        = string
  default     = "openrouter/@preset/heavy"
}

variable "condenser_model" {
  description = "Model for conversation condensation"
  type        = string
  default     = "openrouter/@preset/general"
}

variable "reflection_model" {
  description = "Model for reflection engine"
  type        = string
  default     = "openrouter/@preset/general"
}

variable "orchestrator_subagent_model" {
  description = "Model for orchestrator subagents"
  type        = string
  default     = "openrouter/@preset/standard"
}

variable "orchestrator_analysis_model" {
  description = "Model for parallel analysis"
  type        = string
  default     = "openrouter/@preset/air"
}

variable "orchestrator_synthesis_model" {
  description = "Model for synthesis of analysis results"
  type        = string
  default     = "openrouter/@preset/standard"
}

variable "research_agent_model" {
  description = "Model for research agent"
  type        = string
  default     = "openrouter/@preset/research"
}

variable "diary_signal_model" {
  description = "Model for diary signal computation"
  type        = string
  default     = "openrouter/@preset/air"
}

# =============================================================================
# Orchestrator Configuration
# =============================================================================

variable "orchestrator_max_turns" {
  description = "Maximum turns per orchestrator subagent"
  type        = number
  default     = 15
}

variable "orchestrator_analysis_max_turns" {
  description = "Maximum turns for analysis subagents"
  type        = number
  default     = 10
}

variable "message_window" {
  description = "Recent messages for context"
  type        = number
  default     = 8
}

variable "context_condense_threshold" {
  description = "Context size threshold for condensation"
  type        = number
  default     = 250000
}

# =============================================================================
# Channel Configuration
# =============================================================================

variable "channel_debounce_seconds" {
  description = "Message batching window (seconds)"
  type        = number
  default     = 30
}

variable "channel_max_chunk_chars" {
  description = "Max chars per response chunk"
  type        = number
  default     = 1500
}

variable "openwebui_poll_interval" {
  description = "OpenWebUI polling interval (seconds)"
  type        = number
  default     = 5.0
}

# =============================================================================
# Heartbeat Configuration
# =============================================================================

variable "heartbeat_enabled" {
  description = "Enable heartbeat system"
  type        = bool
  default     = true
}

variable "heartbeat_idle_hours" {
  description = "Hours of inactivity before heartbeat"
  type        = number
  default     = 6.0
}

variable "heartbeat_cooldown_hours" {
  description = "Hours between heartbeats on same channel"
  type        = number
  default     = 6.0
}

variable "heartbeat_quiet_hours" {
  description = "UTC time range to skip heartbeats"
  type        = string
  default     = "23:00-07:00"
}

# =============================================================================
# Reflection Configuration
# =============================================================================

variable "reflection_enabled" {
  description = "Enable reflection engine"
  type        = bool
  default     = true
}

variable "reflection_periodic_hours" {
  description = "Hours between periodic reflections"
  type        = number
  default     = 6.0
}

variable "reflection_post_session_min_turns" {
  description = "Minimum turns before post-session reflection"
  type        = number
  default     = 5
}

variable "reflection_threshold_uncategorized" {
  description = "Uncategorized facts to trigger reflection"
  type        = number
  default     = 20
}

# =============================================================================
# Terminal Configuration
# =============================================================================

variable "terminal_image" {
  description = "Docker image for terminal containers"
  type        = string
  default     = "ghcr.io/open-webui/open-terminal:latest"
}

variable "terminal_network" {
  description = "Docker network for terminals"
  type        = string
  default     = "if-terminal-net"
}

variable "terminal_mem_limit" {
  description = "Memory limit per terminal container"
  type        = string
  default     = "512m"
}

variable "terminal_cpu_quota" {
  description = "CPU quota for terminal containers"
  type        = number
  default     = 50000
}

variable "terminal_idle_timeout" {
  description = "Seconds before idle terminal cleanup"
  type        = number
  default     = 3600
}

variable "terminal_startup_timeout" {
  description = "Seconds to wait for terminal startup"
  type        = number
  default     = 30
}

variable "terminal_max_containers" {
  description = "Maximum concurrent terminal containers"
  type        = number
  default     = 20
}

# =============================================================================
# User/Operator Configuration
# =============================================================================

variable "health_program_pk" {
  description = "Partition key for health program storage"
  type        = string
  default     = "operator"
}

variable "if_user_pk" {
  description = "Default user PK for infrastructure tables"
  type        = string
  default     = "operator"
}

variable "diary_ttl_days" {
  description = "TTL for diary entries (days)"
  type        = number
  default     = 3
}

variable "diary_signal_compute_interval_hours" {
  description = "Interval for automatic signal computation (hours)"
  type        = number
  default     = 6.0
}

# =============================================================================
# Logging Configuration
# =============================================================================

variable "log_level" {
  description = "Logging level"
  type        = string
  default     = "INFO"
}

# =============================================================================
# Persistent Storage Configuration
# =============================================================================

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

# =============================================================================
# Resource limits - Portals
# =============================================================================

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

