"""Configuration module for Discord Webhook Server.

Loads environment variables and defines constants.
"""
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


# Discord Configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not DISCORD_BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN environment variable is required")

# LLM Configuration (reuse main app's patterns)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY environment variable is required")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")

# OpenRouter headers (from main app config pattern)
OPENROUTER_HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/discord-webhook-server",
    "X-Title": "Discord Webhook Server"
}

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

# History Configuration
DEFAULT_HISTORY_LIMIT = int(os.getenv("DEFAULT_HISTORY_LIMIT", "50"))
MAX_HISTORY_LIMIT = int(os.getenv("MAX_HISTORY_LIMIT", "500"))

# Streaming Configuration
STREAM_TIMEOUT = float(os.getenv("STREAM_TIMEOUT", "120.0"))

# Default model for LLM calls
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "openrouter/@preset/general")

# Response chunking (from main app CHANNEL_MAX_CHUNK_CHARS)
MAX_CHUNK_CHARS = int(os.getenv("MAX_CHUNK_CHARS", "1500"))
INTER_CHUNK_DELAY = float(os.getenv("INTER_CHUNK_DELAY", "0.5"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
