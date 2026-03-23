# Kubernetes Secrets for IF Agent API

data "aws_ecr_authorization_token" "private" {}

locals {
  ecr_registry_server  = replace(data.aws_ecr_authorization_token.private.proxy_endpoint, "https://", "")
  ecr_registry_auth    = base64encode("${data.aws_ecr_authorization_token.private.user_name}:${data.aws_ecr_authorization_token.private.password}")
  ecr_dockerconfigjson = <<-EOT
{
  "auths": {
    "${local.ecr_registry_server}": {
      "username": "${data.aws_ecr_authorization_token.private.user_name}",
      "password": "${data.aws_ecr_authorization_token.private.password}",
      "email": "none",
      "auth": "${local.ecr_registry_auth}"
    }
  }
}
EOT
}

# Private ECR image pull secret for k3s
resource "kubernetes_secret" "ecr_registry" {
  metadata {
    name      = "ecr-registry"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  data = {
    ".dockerconfigjson" = local.ecr_dockerconfigjson
  }

  type = "kubernetes.io/dockerconfigjson"
}

# Main API Secrets - sensitive values only
resource "kubernetes_secret" "if_agent_api_secrets" {
  metadata {
    name      = "if-agent-api-secrets"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  data = {
    OPENROUTER_API_KEY = var.openrouter_api_key
    DISCORD_TOKEN      = var.discord_token
  }

  type = "Opaque"
}

# Main API ConfigMap - non-sensitive configuration
resource "kubernetes_config_map" "if_agent_api_config" {
  metadata {
    name      = "if-agent-api-config"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  data = {
    # DynamoDB Tables
    IF_CORE_TABLE_NAME          = var.dynamodb_core_table
    IF_HEALTH_TABLE_NAME        = var.dynamodb_health_table
    IF_FINANCE_TABLE_NAME       = var.dynamodb_finance_table
    IF_DIARY_ENTRIES_TABLE_NAME = var.dynamodb_diary_entries_table
    IF_DIARY_SIGNALS_TABLE_NAME = var.dynamodb_diary_signals_table
    IF_PROPOSALS_TABLE_NAME     = var.dynamodb_proposals_table

    # Model configuration
    API_MODEL_NAME  = var.api_model_name
    TOKENIZER_MODEL = var.tokenizer_model
    EMBEDDING_MODEL = var.embedding_model

    # Preset models
    DIRECTIVE_REWRITE_MODEL = var.directive_rewrite_model
    CONDENSER_MODEL         = var.condenser_model
    REFLECTION_MODEL        = var.reflection_model
    RESEARCH_AGENT_MODEL    = var.research_agent_model
    DIARY_SIGNAL_MODEL      = var.diary_signal_model

    # Tiering configuration
    TIER_UPGRADE_THRESHOLD = tostring(var.tier_upgrade_threshold)
    TIER_AIR_LIMIT         = tostring(var.tier_air_limit)
    TIER_STANDARD_LIMIT    = tostring(var.tier_standard_limit)
    TIER_HEAVY_LIMIT       = tostring(var.tier_heavy_limit)
    TIER_AIR_PRESET        = var.tier_air_preset
    TIER_STANDARD_PRESET   = var.tier_standard_preset
    TIER_HEAVY_PRESET      = var.tier_heavy_preset

    # Specialist configuration
    SPECIALIST_PRESET    = var.specialist_preset
    SPECIALIST_MAX_TURNS = tostring(var.specialist_max_turns)
    THINKING_PRESET      = var.thinking_preset
    THINKING_MAX_TURNS   = tostring(var.thinking_max_turns)

    # Orchestrator configuration
    ORCHESTRATOR_MAX_TURNS          = tostring(var.orchestrator_max_turns)
    ORCHESTRATOR_ANALYSIS_MAX_TURNS = tostring(var.orchestrator_analysis_max_turns)

    # Context configuration
    CONTEXT_CONDENSE_THRESHOLD = tostring(var.context_condense_threshold)
    MESSAGE_WINDOW             = tostring(var.message_window)

    # Server configuration
    HOST = "0.0.0.0"
    PORT = "8000"

    # Channel configuration
    CHANNEL_DEBOUNCE_SECONDS = tostring(var.channel_debounce_seconds)
    CHANNEL_MAX_CHUNK_CHARS  = tostring(var.channel_max_chunk_chars)
    OPENWEBUI_POLL_INTERVAL  = tostring(var.openwebui_poll_interval)

    # Heartbeat configuration
    HEARTBEAT_ENABLED        = tostring(var.heartbeat_enabled)
    HEARTBEAT_IDLE_HOURS     = tostring(var.heartbeat_idle_hours)
    HEARTBEAT_COOLDOWN_HOURS = tostring(var.heartbeat_cooldown_hours)
    HEARTBEAT_QUIET_HOURS    = var.heartbeat_quiet_hours

    # Reflection configuration
    REFLECTION_ENABLED                 = tostring(var.reflection_enabled)
    REFLECTION_PERIODIC_HOURS          = tostring(var.reflection_periodic_hours)
    REFLECTION_POST_SESSION_MIN_TURNS  = tostring(var.reflection_post_session_min_turns)
    REFLECTION_THRESHOLD_UNCATEGORIZED = tostring(var.reflection_threshold_uncategorized)

    # Terminal configuration (K8s mode - uses pods instead of docker)
    TERMINAL_IMAGE           = var.terminal_image
    TERMINAL_MEM_LIMIT       = var.terminal_mem_limit
    TERMINAL_CPU_QUOTA       = tostring(var.terminal_cpu_quota)
    TERMINAL_IDLE_TIMEOUT    = tostring(var.terminal_idle_timeout)
    TERMINAL_STARTUP_TIMEOUT = tostring(var.terminal_startup_timeout)
    TERMINAL_MAX_CONTAINERS  = tostring(var.terminal_max_containers)

    # Health configuration
    HEALTH_PROGRAM_PK = var.health_program_pk

    # User configuration
    IF_USER_PK = var.if_user_pk

    # Diary configuration
    DIARY_TTL_DAYS                      = tostring(var.diary_ttl_days)
    DIARY_SIGNAL_COMPUTE_INTERVAL_HOURS = tostring(var.diary_signal_compute_interval_hours)

    # AWS Region
    AWS_REGION = var.region

    # Logging
    LOG_LEVEL = var.log_level
  }
}

# =============================================================================
# Portal Backend ConfigMaps
# =============================================================================

# Main Portal ConfigMap (hub that proxies to other portal backends)
resource "kubernetes_config_map" "main_portal_config" {
  metadata {
    name      = "main-portal-config"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  data = {
    NODE_ENV             = "production"
    PORT                 = "3000"
    FINANCE_PORTAL_URL   = "http://finance-portal-backend:3002"
    HEALTH_PORTAL_URL    = "http://powerlifting-app-backend:3005"
    DIARY_PORTAL_URL     = "http://diary-portal-backend:3003"
    PROPOSALS_PORTAL_URL = "http://proposals-portal-backend:3004"
    FRONTEND_URL         = "http://main-portal-frontend:3001"
  }
}

# Finance Portal ConfigMap
resource "kubernetes_config_map" "finance_portal_config" {
  metadata {
    name      = "finance-portal-config"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  data = {
    AWS_REGION     = var.region
    DYNAMODB_TABLE = var.dynamodb_finance_table
    NODE_ENV       = "production"
    PORT           = "3002"
    FRONTEND_URL   = "http://finance-portal-frontend:3001"
  }
}

# Diary Portal ConfigMap
resource "kubernetes_config_map" "diary_portal_config" {
  metadata {
    name      = "diary-portal-config"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  data = {
    AWS_REGION     = var.region
    DYNAMODB_TABLE = var.dynamodb_diary_entries_table
    NODE_ENV       = "production"
    PORT           = "3003"
    FRONTEND_URL   = "http://diary-portal-frontend:3001"
  }
}

# Proposals Portal ConfigMap
resource "kubernetes_config_map" "proposals_portal_config" {
  metadata {
    name      = "proposals-portal-config"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  data = {
    AWS_REGION     = var.region
    DYNAMODB_TABLE = var.dynamodb_proposals_table
    NODE_ENV       = "production"
    PORT           = "3004"
    FRONTEND_URL   = "http://proposals-portal-frontend:3001"
  }
}

# Powerlifting App ConfigMap
resource "kubernetes_config_map" "powerlifting_app_config" {
  metadata {
    name      = "powerlifting-app-config"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  data = {
    AWS_REGION     = var.region
    DYNAMODB_TABLE = var.dynamodb_powerlifting_table
    NODE_ENV       = "production"
    PORT           = "3005"
    FRONTEND_URL   = "http://powerlifting-app-frontend:3001"
  }
}

