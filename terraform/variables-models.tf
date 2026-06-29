variable "tier_upgrade_threshold" {
  description = "Fraction of context limit before tier upgrade"
  type        = number
  default     = 0.65
}

variable "if_agent_api_model_env" {
  description = "Model, router, tier, and model-adjacent environment variables for the IF agent API pod. ConfigMap values must be strings."
  type        = map(string)
  default     = {}
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
  description = "Model for suggestions and title generation"
  type        = string
  default     = "mistralai/mistral-nemo"
}

variable "directive_rewrite_model" {
  description = "Model for directive content rewriting"
  type        = string
  default     = "openrouter/@preset/heavy"
}

variable "model_router_model" {
  description = "Fast model for subagent routing"
  type        = string
  default     = "anthropic/claude-haiku-4.5"
}

variable "health_helper_model" {
  description = "Cheaper model for narrow powerlifting helper flows"
  type        = string
  default     = "openai/gpt-5.4-mini"
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