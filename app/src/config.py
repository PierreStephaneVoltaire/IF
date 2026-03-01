"""Configuration module for IF Prototype A1.

Loads environment variables and defines constants for the API server.
"""
import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# ============================================================================
# Required Environment Variables
# ============================================================================

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY environment variable is required")

LLM_API_KEY = os.getenv("LLM_API_KEY", OPENROUTER_API_KEY)  # Default to OPENROUTER_API_KEY


# ============================================================================
# Optional Environment Variables with Defaults
# ============================================================================

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

# ============================================================================
# MCP Server API Keys Configuration
# ============================================================================

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


# ============================================================================
# OpenRouter API Configuration
# ============================================================================

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/if-prototype-a1",
    "X-Title": "IF Prototype A1"
}


# ============================================================================
# OpenWebUI Task Detection
# ============================================================================

OPENWEBUI_TASK_MARKERS = [
    "### Task:\nSuggest 3-5 relevant follow-up",
    "### Task:\nGenerate a concise, 3-5 word title",
    "### Task:\nGenerate 1-3 broad tags",
]


# ============================================================================
# MCP Server Configuration (Deprecated - use mcp_servers.config instead)
# ============================================================================

# This is kept for backward compatibility but should be imported from mcp_servers.config
PRESET_MCP_MAP = {
    "__all__": ["time"],  # Memory tools are registered separately, not via MCP
    "architecture": ["aws_docs", "sandbox"],
    "coding": ["sandbox"],
    "health": ["google_sheets"],
    "mental_health": [],  # No MCP servers for mental health
    "social": [],  # No MCP servers for social
    "finance": ["yahoo_finance", "alpha_vantage"],  # Finance preset gets stock data servers
}

