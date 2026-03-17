"""FastAPI main application for Discord Webhook Server.

Minimal wrapper that:
1. Initializes Discord client
2. Sets up HTTP client for LLM calls
3. Includes channel registration router
"""
from __future__ import annotations
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI

from config import HOST, PORT, LOG_LEVEL, DISCORD_BOT_TOKEN
from routers import channels

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global HTTP client for LLM calls
http_client: Optional[httpx.AsyncClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global http_client

    logger.info("Starting Discord Webhook Server...")

    # Initialize HTTP client for LLM calls
    http_client = httpx.AsyncClient(
        timeout=120.0,
        limits=httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
            keepalive_expiry=60.0
        )
    )
    app.state.http_client = http_client
    logger.info("HTTP client initialized")

    # Start Discord client
    from discord_client import start_client
    try:
        client = start_client(DISCORD_BOT_TOKEN)
        app.state.discord_client = client
        logger.info("Discord client started")
    except Exception as e:
        logger.error(f"Failed to start Discord client: {e}")
        raise

    logger.info(f"Server ready on {HOST}:{PORT}")

    yield

    # Shutdown
    logger.info("Shutting down...")

    from discord_client import stop_client
    stop_client()
    logger.info("Discord client stopped")

    if http_client:
        await http_client.aclose()
        logger.info("HTTP client closed")


app = FastAPI(
    title="Discord Webhook Server",
    description="FastAPI server for Discord channel webhooks with LLM streaming",
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(channels.router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from discord_client import get_client

    try:
        client = get_client()
        discord_ready = client.is_ready()
        registered_count = len(client.registered_channels)
    except Exception:
        discord_ready = False
        registered_count = 0

    return {
        "status": "healthy" if discord_ready else "degraded",
        "service": "discord-webhook-server",
        "discord_connected": discord_ready,
        "registered_channels": registered_count,
    }


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Discord Webhook Server",
        "version": "0.1.0",
        "endpoints": {
            "channels": "/channels/",
            "health": "/health",
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=True
    )
