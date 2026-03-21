"""Configuration module for Discord Webhook Server.

Loads environment variables and defines constants.
"""
import os
from dotenv import load_dotenv

load_dotenv()


# Discord Configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not DISCORD_BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN environment variable is required")

# Agent API Configuration
# URL of the main agent FastAPI server (app/src/main.py)
AGENT_API_URL = os.getenv("AGENT_API_URL", "http://localhost:8000")
if not AGENT_API_URL:
    raise ValueError("AGENT_API_URL environment variable is required")

# The model name the main agent expects (must match API_MODEL_NAME in app/src/config.py)
AGENT_MODEL_NAME = os.getenv("AGENT_MODEL_NAME", "if-prototype")

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

# History Configuration
DEFAULT_HISTORY_LIMIT = int(os.getenv("DEFAULT_HISTORY_LIMIT", "50"))
MAX_HISTORY_LIMIT = int(os.getenv("MAX_HISTORY_LIMIT", "500"))

# Request timeout for agent API calls (seconds)
AGENT_TIMEOUT = float(os.getenv("AGENT_TIMEOUT", "120.0"))

# Response chunking (Discord has a 2000 char message limit)
MAX_CHUNK_CHARS = int(os.getenv("MAX_CHUNK_CHARS", "1500"))
INTER_CHUNK_DELAY = float(os.getenv("INTER_CHUNK_DELAY", "0.5"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
