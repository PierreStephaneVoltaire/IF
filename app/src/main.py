"""FastAPI main application for IF Prototype A1.

This module implements the OpenAI-compatible API server with intelligent
routing to OpenRouter presets based on conversation analysis.
"""
from __future__ import annotations
import asyncio
import uuid
from typing import Optional
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, PlainTextResponse

from config import HOST, PORT, SANDBOX_PATH, MEMORY_DB_PATH, PERSISTENCE_DIR, STORAGE_DB_PATH
from config import HEARTBEAT_ENABLED, HEARTBEAT_IDLE_HOURS, HEARTBEAT_COOLDOWN_HOURS
from api.models import router as models_router
from api.completions import router as completions_router
from api.files import router as files_router, get_sandbox_directory
from api.webhooks import router as webhooks_router
from presets.loader import get_preset_manager
from mcp_servers.config import validate_mcp_config
from storage.factory import init_store, close_store, get_webhook_store
from channels.debounce import init_debounce
from channels.manager import start_all_active, stop_all


# Shared HTTP client for connection pooling
http_client: Optional[httpx.AsyncClient] = None

# Heartbeat runner (global for health check access)
heartbeat_runner = None


async def _deliver_heartbeat(webhook, content: str, attachments: list) -> None:
    """Deliver a heartbeat message to a channel.
    
    Args:
        webhook: Target webhook record
        content: Message content
        attachments: List of attachments
    """
    import logging
    logger = logging.getLogger(__name__)
    
    from channels.delivery import deliver_to_channel
    from channels.chunker import chunk_response
    
    config = webhook.get_config()
    platform = webhook.platform
    channel_id = config.get("channel_id", webhook.conversation_id)
    
    logger.info(f"[Heartbeat] Delivering to {webhook.label} (channel_id={channel_id})")
    
    # Create a minimal channel reference based on platform
    if platform == "discord":
        # For Discord, we need to use the Discord client directly
        # The channel_ref from Discord is a TextChannel object
        try:
            from channels.listeners.discord_listener import get_discord_client
            client = get_discord_client()
            if client:
                # Find the channel by ID
                import discord
                channel = client.get_channel(int(channel_id))
                if channel and isinstance(channel, discord.TextChannel):
                    chunks = chunk_response(content)
                    await deliver_to_channel(
                        platform=platform,
                        channel_ref=channel,
                        chunks=chunks,
                        attachments=attachments,
                    )
                    return
        except Exception as e:
            logger.warning(f"[Heartbeat] Discord delivery failed: {e}")
            return
    
    elif platform == "openwebui":
        # For OpenWebUI, use the API URL from config
        from channels.delivery import deliver_to_openwebui
        chunks = chunk_response(content)
        await deliver_to_openwebui(
            api_url=config.get("api_url"),
            channel_id=channel_id,
            chunks=chunks,
            attachments=attachments,
        )
        return
    
    logger.warning(f"[Heartbeat] Unknown platform: {platform}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown.
    
    Startup:
    - Initialize HTTP client
    - Load presets from OpenRouter
    - Create necessary directories
    - Validate MCP configuration
    - Initialize memory store
    
    Shutdown:
    - Close HTTP client
    """
    global http_client
    
    # Startup
    print("[Startup] Initializing IF Prototype A1...")
    
    # Initialize HTTP client
    http_client = httpx.AsyncClient(
        timeout=120.0,
        limits=httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
            keepalive_expiry=60.0
        )
    )
    app.state.http_client = http_client
    print(f"[Startup] HTTP client initialized")
    
    # Load static presets
    print("[Startup] Loading presets...")
    preset_manager = get_preset_manager()
    try:
        preset_manager.load_presets()
    except RuntimeError as e:
        print(f"[Startup] ERROR: {e}")
        raise
    
    # Create necessary directories
    sandbox_dir = get_sandbox_directory()
    print(f"[Startup] Sandbox directory: {sandbox_dir}")
    
    # Create memory database directory
    memory_db_path = Path(MEMORY_DB_PATH)
    memory_db_path.mkdir(parents=True, exist_ok=True)
    print(f"[Startup] Memory database directory: {memory_db_path}")
    
    # Create conversation persistence directory
    persistence_path = Path(PERSISTENCE_DIR)
    persistence_path.mkdir(parents=True, exist_ok=True)
    print(f"[Startup] Conversation persistence directory: {persistence_path}")
    
    # Validate MCP configuration
    try:
        validate_mcp_config()
        print(f"[Startup] MCP configuration validated")
    except ValueError as e:
        print(f"[Startup] WARNING: MCP configuration error: {e}")
    
    # Initialize memory store (creates ChromaDB collection if needed)
    # Try new UserFactStore first, fall back to legacy MemoryStore
    try:
        from .memory import get_user_fact_store
        user_facts_store = get_user_fact_store()
        facts_count = user_facts_store.active_count
        print(f"[Startup] User facts store initialized ({facts_count} active facts)")
        
        # Warm up the embedding model to prevent runtime download delays
        # This triggers ChromaDB to load the ONNX embedding model
        print(f"[Startup] Warming up embedding model...")
        try:
            # Perform a dummy search to trigger model loading
            user_facts_store.search("__warmup_query__", limit=1)
            print(f"[Startup] Embedding model ready")
        except Exception as warmup_error:
            print(f"[Startup] WARNING: Embedding model warmup failed: {warmup_error}")
    except ImportError as e:
        print(f"[Startup] WARNING: User facts store not available: {e}")
        print(f"[Startup] Install chromadb to enable user facts: pip install chromadb")
    except Exception as e:
        print(f"[Startup] WARNING: User facts store initialization failed: {e}")
    
    # Also initialize legacy memory store for backward compatibility
    try:
        from .memory import get_memory_store
        if get_memory_store:
            memory_store = get_memory_store()
            memory_count = memory_store.count()
            print(f"[Startup] Legacy memory store initialized ({memory_count} memories)")
    except ImportError:
        pass  # Legacy store not available, that's OK
    except Exception as e:
        print(f"[Startup] WARNING: Legacy memory store initialization failed: {e}")
    
    # Ensure NLTK stopwords are available for topic shift heuristic
    try:
        import nltk
        nltk.data.find("corpora/stopwords")
        print(f"[Startup] NLTK stopwords corpus found")
    except LookupError:
        print(f"[Startup] Downloading NLTK stopwords corpus...")
        import nltk
        nltk.download("stopwords", quiet=True)
        print(f"[Startup] NLTK stopwords downloaded")
    except ImportError:
        print(f"[Startup] WARNING: nltk not installed, topic shift heuristic will use basic filtering")
    
    # Initialize storage backend (SQLite with WAL mode)
    try:
        # Ensure storage database directory exists
        storage_db_path = Path(STORAGE_DB_PATH)
        storage_db_path.parent.mkdir(parents=True, exist_ok=True)
        init_store()
        print(f"[Startup] Storage backend initialized at {STORAGE_DB_PATH}")
    except Exception as e:
        print(f"[Startup] ERROR: Storage initialization failed: {e}")
        raise
    
    # Initialize debounce system for channel messages
    try:
        init_debounce(asyncio.get_running_loop())
        print(f"[Startup] Debounce system initialized")
    except Exception as e:
        print(f"[Startup] WARNING: Debounce initialization failed: {e}")
    
    # Resume active channel listeners from persisted state
    try:
        store = get_webhook_store()
        active_records = store.list_active()
        start_all_active(active_records)
        print(f"[Startup] Resumed {len(active_records)} active channel listeners")
    except Exception as e:
        print(f"[Startup] WARNING: Failed to resume listeners: {e}")
    
    # Initialize heartbeat system
    global heartbeat_runner
    if HEARTBEAT_ENABLED:
        try:
            from heartbeat.activity import ActivityTracker
            from heartbeat.runner import HeartbeatRunner
            
            store = get_webhook_store()
            activity_tracker = ActivityTracker(store._backend)
            
            # Get user facts store (may not be available if chromadb not installed)
            try:
                from .memory import get_user_fact_store
                user_facts_store = get_user_fact_store()
            except Exception:
                user_facts_store = None
            
            # Get conversation cache
            from routing.cache import get_cache
            conversation_cache = get_cache()
            
            heartbeat_runner = HeartbeatRunner(
                activity_tracker=activity_tracker,
                webhook_store=store,
                user_facts_store=user_facts_store,
                conversation_cache=conversation_cache,
                http_client=http_client,
            )
            
            # Set delivery function for heartbeat messages
            heartbeat_runner.set_deliver_fn(_deliver_heartbeat)
            
            heartbeat_runner.start()
            print(f"[Startup] Heartbeat system started (idle={HEARTBEAT_IDLE_HOURS}h, cooldown={HEARTBEAT_COOLDOWN_HOURS}h)")
        except Exception as e:
            print(f"[Startup] WARNING: Heartbeat initialization failed: {e}")
    
    print(f"[Startup] Server ready on {HOST}:{PORT}")
    
    yield
    
    # Shutdown
    # Stop heartbeat runner first
    if heartbeat_runner:
        heartbeat_runner.stop()
        print("[Shutdown] Heartbeat runner stopped")
    
    stop_all()
    print("[Shutdown] All channel listeners stopped")
    
    close_store()
    print("[Shutdown] Storage backend closed")
    
    if http_client:
        await http_client.aclose()
        print("[Shutdown] HTTP client closed")


# Create FastAPI app
app = FastAPI(
    title="IF Prototype A1 - Agent API",
    description="OpenAI-compatible API with intelligent routing to OpenRouter presets",
    version="0.1.0",
    lifespan=lifespan,
)


# ============================================================================
# Include Routers
# ============================================================================

# API endpoints
app.include_router(models_router)
app.include_router(completions_router)
app.include_router(files_router)
app.include_router(webhooks_router)


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint with feature status."""
    preset_manager = get_preset_manager()
    
    # Check user facts store status
    user_facts_status = "unavailable"
    user_facts_count = 0
    try:
        from .memory import get_user_fact_store
        store = get_user_fact_store()
        user_facts_status = "active"
        user_facts_count = store.active_count
    except Exception:
        pass
    
    # Check legacy memory store status
    memory_status = "unavailable"
    memory_count = 0
    try:
        from .memory import get_memory_store
        store = get_memory_store()
        memory_status = "active"
        memory_count = store.count()
    except Exception:
        pass
    
    # Check channel system status
    from channels.manager import get_active_listener_count
    from channels.debounce import get_all_buffer_sizes
    active_listeners = get_active_listener_count()
    buffer_sizes = get_all_buffer_sizes()
    
    # Check routing cache status
    from routing.cache import get_cache
    cache = get_cache()
    cached_conversations = len(cache._cache)
    pinned_conversations = sum(1 for v in cache._cache.values() if v.pinned)
    
    # Check heartbeat status
    heartbeat_status = "inactive"
    if heartbeat_runner and heartbeat_runner._task:
        heartbeat_status = "active"
    
    return {
        "status": "healthy",
        "service": "if-prototype-a1",
        "features": {
            "routing": "active",
            "interceptor": "active",
            "commands": "active",
            "attachments": "active",
            "user_facts_store": user_facts_status,
            "user_facts_count": user_facts_count,
            "presets_loaded": preset_manager.is_initialized(),
            "preset_count": len(preset_manager.get_all_presets()),
            "channel_system": "active",
            "active_listeners": active_listeners,
            "pending_messages": sum(buffer_sizes.values()),
            "heartbeat": heartbeat_status,
            "heartbeat_idle_hours": HEARTBEAT_IDLE_HOURS if HEARTBEAT_ENABLED else None,
            "cached_conversations": cached_conversations,
            "pinned_conversations": pinned_conversations,
        }
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "IF Prototype A1 - Agent API",
        "version": "0.1.0",
        "description": "OpenAI-compatible API with intelligent routing to OpenRouter presets",
        "endpoints": {
            "models": "/v1/models",
            "chat": "/v1/chat/completions",
            "health": "/health",
            "files": "/files/sandbox/{filepath}",
            "webhooks": "/v1/webhooks/",
        }
    }


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=True
    )
