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

variable "tool_output_char_limit" {
  description = "Max chars for tool output before SDK truncation (default SDK is 50000)"
  type        = number
  default     = 200000
}

variable "channel_debounce_seconds" {
  description = "Message batching window (seconds)"
  type        = number
  default     = 5
}

variable "llm_reasoning_effort" {
  description = "Reasoning effort for the main agent LLM (high/medium/low)"
  type        = string
  default     = "high"
}

variable "channel_max_chunk_chars" {
  description = "Max chars per response chunk"
  type        = number
  default     = 1500
}

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

variable "terminal_network" {
  description = "Docker network for terminals"
  type        = string
  default     = "if-terminal-net"
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

variable "terminal_storage_gb" {
  description = "Storage size for terminal workspace (GB)"
  type        = number
  default     = 10
}

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