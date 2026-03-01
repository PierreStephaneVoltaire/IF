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
from api.models import router as models_router
from api.completions import router as completions_router
from api.files import router as files_router, get_sandbox_directory
from presets.loader import get_preset_manager
from mcp_servers.config import validate_mcp_config
from storage.factory import init_store, close_store


# Shared HTTP client for connection pooling
http_client: Optional[httpx.AsyncClient] = None


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
    try:
        from .memory import get_memory_store
        memory_store = get_memory_store()
        memory_count = memory_store.count()
        print(f"[Startup] Memory store initialized ({memory_count} memories)")
    except ImportError as e:
        print(f"[Startup] WARNING: Memory store not available: {e}")
        print(f"[Startup] Install chromadb to enable memory: pip install chromadb")
    except Exception as e:
        print(f"[Startup] WARNING: Memory store initialization failed: {e}")
    
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
    
    print(f"[Startup] Server ready on {HOST}:{PORT}")
    
    yield
    
    # Shutdown
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


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    preset_manager = get_preset_manager()
    
    # Check memory store status
    memory_status = "unavailable"
    memory_count = 0
    try:
        from .memory import get_memory_store
        store = get_memory_store()
        memory_status = "active"
        memory_count = store.count()
    except Exception:
        pass
    
    return {
        "status": "healthy",
        "service": "if-prototype-a1",
        "features": {
            "routing": "partial",  # Only Step 1 implemented
            "interceptor": "active",
            "attachments": "active",
            "memory_store": memory_status,
            "memory_count": memory_count,
            "presets_loaded": preset_manager.is_initialized(),
            "preset_count": len(preset_manager.get_all_presets()),
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
