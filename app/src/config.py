"""Configuration module for IF Prototype A1.

Loads environment variables and defines constants for the API server.
"""
import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()




OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY environment variable is required")

LLM_API_KEY = os.getenv("LLM_API_KEY", OPENROUTER_API_KEY)  # Default to OPENROUTER_API_KEY



# LLM Configuration
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")

# Routing Configuration
MESSAGE_WINDOW = int(os.getenv("MESSAGE_WINDOW", "8"))
CRISIS_THRESHOLD = float(os.getenv("CRISIS_THRESHOLD", "0.3"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
CONFIDENCE_GAP = float(os.getenv("CONFIDENCE_GAP", "0.2"))
RECLASSIFY_MESSAGE_COUNT = int(os.getenv("RECLASSIFY_MESSAGE_COUNT", "4"))

# Model Configuration
SUGGESTION_MODEL = os.getenv("SUGGESTION_MODEL", "mistralai/mistral-nemo")

# Parse comma-separated scoring models
SCORING_MODELS_STR = os.getenv(
    "SCORING_MODELS",
    "google/gemini-2.5-flash-lite,openai/gpt-oss-120b,anthropic/claude-haiku-4.5"
)
SCORING_MODELS: List[str] = [
    model.strip() for model in SCORING_MODELS_STR.split(",") if model.strip()
]

MENTAL_HEALTH_PRESET = os.getenv("MENTAL_HEALTH_PRESET", "mental-health")



# Google Sheets MCP server
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")

# Yahoo Finance (no API key required)
# Uses mcp-yahoo-finance package directly

# Alpha Vantage API key for stock data
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "")

# Paths
SANDBOX_PATH = os.getenv("SANDBOX_PATH", "./sandbox")
MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", "./data/memory_db")
PERSISTENCE_DIR = os.getenv("PERSISTENCE_DIR", "./data/conversations")

# Storage Configuration (Phase 2)
STORAGE_DB_PATH = os.getenv("STORAGE_DB_PATH", "./data/store.db")
STORE_BACKEND = os.getenv("STORE_BACKEND", "sqlite")
# Future DynamoDB vars:
# DYNAMODB_WEBHOOK_TABLE = os.getenv("DYNAMODB_WEBHOOK_TABLE", "")
# AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Topic Shift Detection (Phase 1)
TOPIC_SHIFT_MODEL = os.getenv("TOPIC_SHIFT_MODEL", "z-ai/glm-4.7-flash")

# Context Condensation
CONTEXT_CONDENSE_THRESHOLD = int(os.getenv("CONTEXT_CONDENSE_THRESHOLD", "250000"))

# Cache Configuration
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour
MAX_CACHE_SIZE = int(os.getenv("MAX_CACHE_SIZE", "1000"))  # Max conversations in cache

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Channel System Configuration (Phase 5)
CHANNEL_DEBOUNCE_SECONDS = float(os.getenv("CHANNEL_DEBOUNCE_SECONDS", "30"))
CHANNEL_MAX_CHUNK_CHARS = int(os.getenv("CHANNEL_MAX_CHUNK_CHARS", "1500"))
OPENWEBUI_POLL_INTERVAL = float(os.getenv("OPENWEBUI_POLL_INTERVAL", "5.0"))



HEARTBEAT_ENABLED: bool = os.getenv("HEARTBEAT_ENABLED", "true").lower() == "true"
HEARTBEAT_IDLE_HOURS: float = float(os.getenv("HEARTBEAT_IDLE_HOURS", "6.0"))
HEARTBEAT_COOLDOWN_HOURS: float = float(os.getenv("HEARTBEAT_COOLDOWN_HOURS", "6.0"))
HEARTBEAT_QUIET_HOURS: str = os.getenv("HEARTBEAT_QUIET_HOURS", "23:00-07:00")  # UTC



REFLECTION_ENABLED: bool = os.getenv("REFLECTION_ENABLED", "true").lower() == "true"
REFLECTION_PERIODIC_HOURS: float = float(os.getenv("REFLECTION_PERIODIC_HOURS", "6.0"))
REFLECTION_POST_SESSION_MIN_TURNS: int = int(os.getenv("REFLECTION_POST_SESSION_MIN_TURNS", "5"))

# Thresholds for triggering reflection
REFLECTION_THRESHOLD_UNCATEGORIZED: int = int(os.getenv("REFLECTION_THRESHOLD_UNCATEGORIZED", "20"))
REFLECTION_THRESHOLD_GAPS_NO_CRITERIA: int = int(os.getenv("REFLECTION_THRESHOLD_GAPS_NO_CRITERIA", "5"))
REFLECTION_THRESHOLD_OPINIONS_NO_RESPONSE: int = int(os.getenv("REFLECTION_THRESHOLD_OPINIONS_NO_RESPONSE", "10"))

# Capability Gap Promotion (Phase5 - Part5 of plan.md)
CAPABILITY_GAP_PROMOTION_THRESHOLD: int = int(os.getenv("CAPABILITY_GAP_PROMOTION_THRESHOLD", "3"))



OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/if-prototype-a1",
    "X-Title": "IF Prototype A1"
}


OPENWEBUI_TASK_MARKERS = [
    "### Task:\nSuggest 3-5 relevant follow-up",
    "### Task:\nGenerate a concise, 3-5 word title",
    "### Task:\nGenerate 1-3 broad tags",
]


# Part6: This map is deprecated. Import from mcp_servers.config instead.
# The actual PRESET_MCP_MAP is in src/mcp_servers/config.py which has been
# updated to remove the sandbox MCP server.
#
# This is kept only for backward compatibility with any code that hasn't
# been migrated yet. New code should use:
#   from mcp_servers.config import PRESET_MCP_MAP, resolve_mcp_config
#
# Note: Sandbox MCP server removed - terminal tools now provide file access
PRESET_MCP_MAP = {
    "__all__": ["time"],  # Memory tools are registered separately, not via MCP
    "architecture": ["aws_docs"],  # sandbox removed (Part6)
    "code": [],  # sandbox removed (Part6) - use terminal_execute
    "health": ["google_sheets"],
    "mental_health": [],  # No MCP servers for mental health
    "social": [],  # No MCP servers for social
    "finance": ["yahoo_finance", "alpha_vantage"],  # Finance preset gets stock data servers
    "pondering": [],  # Only gets time via __all__
}



DIRECTIVE_STORE_ENABLED: bool = os.getenv("DIRECTIVE_STORE_ENABLED", "true").lower() == "true"
DYNAMODB_DIRECTIVES_TABLE = os.getenv("DYNAMODB_DIRECTIVES_TABLE", "if-core")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Model for directive content rewriting (configurable via env var)
# Examples: "anthropic/claude-opus-4", "anthropic/claude-3.5-sonnet", "openai/gpt-4o"
DIRECTIVE_REWRITE_MODEL = os.getenv("DIRECTIVE_REWRITE_MODEL", "anthropic/claude-opus-4.6")

# Model for conversation condensation (summarizing long conversations)
CONDENSER_MODEL = os.getenv("CONDENSER_MODEL", "anthropic/claude-3-haiku")

# Fallback model for heartbeat pondering (when pondering preset unavailable)
HEARTBEAT_FALLBACK_MODEL = os.getenv("HEARTBEAT_FALLBACK_MODEL", "openai/gpt-4o-mini")

# Fallback model for presets without defined models
PRESET_FALLBACK_MODEL = os.getenv("PRESET_FALLBACK_MODEL", "anthropic/claude-3.5-sonnet")

# Model for reflection engine and opinion formation
REFLECTION_MODEL = os.getenv("REFLECTION_MODEL", "openrouter/@preset/general")


TERMINAL_IMAGE = os.getenv("TERMINAL_IMAGE", "ghcr.io/open-webui/open-terminal:latest")
TERMINAL_NETWORK = os.getenv("TERMINAL_NETWORK", "if-terminal-net")
TERMINAL_MEM_LIMIT = os.getenv("TERMINAL_MEM_LIMIT", "512m")
TERMINAL_CPU_QUOTA = int(os.getenv("TERMINAL_CPU_QUOTA", "50000"))
TERMINAL_IDLE_TIMEOUT = int(os.getenv("TERMINAL_IDLE_TIMEOUT", "3600"))
TERMINAL_STARTUP_TIMEOUT = float(os.getenv("TERMINAL_STARTUP_TIMEOUT", "30.0"))
TERMINAL_MAX_CONTAINERS = int(os.getenv("TERMINAL_MAX_CONTAINERS", "20"))

# Docker named volumes host root path (for file serving)
# On standard Docker installs this is /var/lib/docker/volumes/
# Set to empty string to disable direct host access (will use docker cp fallback)
TERMINAL_VOLUME_HOST_ROOT = os.getenv("TERMINAL_VOLUME_HOST_ROOT", "/var/lib/docker/volumes")



# Model for plan execution subagents
ORCHESTRATOR_SUBAGENT_MODEL = os.getenv("ORCHESTRATOR_SUBAGENT_MODEL", "anthropic/claude-sonnet-4")

# Model for parallel analysis subagents (lighter weight for faster analysis)
ORCHESTRATOR_ANALYSIS_MODEL = os.getenv("ORCHESTRATOR_ANALYSIS_MODEL", "anthropic/claude-haiku-4.5")

# Model for synthesis of parallel analysis results
ORCHESTRATOR_SYNTHESIS_MODEL = os.getenv("ORCHESTRATOR_SYNTHESIS_MODEL", "anthropic/claude-sonnet-4")

# Maximum turns per subagent before timeout
ORCHESTRATOR_MAX_TURNS = int(os.getenv("ORCHESTRATOR_MAX_TURNS", "15"))

# Maximum turns for analysis subagents (usually need fewer)
ORCHESTRATOR_ANALYSIS_MAX_TURNS = int(os.getenv("ORCHESTRATOR_ANALYSIS_MAX_TURNS", "10"))


# =============================================================================
# Health Module Configuration
# =============================================================================

# DynamoDB table name for health program storage
# Note: IF_HEALTH_TABLE_NAME is defined at line 8 in .env.example
IF_HEALTH_TABLE_NAME = os.getenv("IF_HEALTH_TABLE_NAME", "if-health")

# Partition key value for health program storage
HEALTH_PROGRAM_PK = os.getenv("HEALTH_PROGRAM_PK", "operator")

# Directory containing health PDF documents for RAG
HEALTH_DOCS_DIR = os.getenv("HEALTH_DOCS_DIR", "docs/health")

# Model for research agent spawned by health tools
RESEARCH_AGENT_MODEL = os.getenv("RESEARCH_AGENT_MODEL", "anthropic/claude-opus-4-5")


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "./logs/app.log")

