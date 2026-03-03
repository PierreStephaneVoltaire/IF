"""Factory function that returns the correct store backend.

Based on environment configuration.

Currently: SQLite only.
Future: Add DynamoDB branch when migrating to AWS.
"""
from __future__ import annotations
import logging
from typing import Optional

from config import STORE_BACKEND
from storage.protocol import WebhookStore


logger = logging.getLogger(__name__)

# Global store instance
_store: Optional[WebhookStore] = None


def init_store() -> None:
    """Initialize the configured storage backend.
    
    Called at startup. Initializes the backend based on STORE_BACKEND env var.
    """
    global _store

    if STORE_BACKEND == "sqlite":
        from storage.sqlite_backend import init_sqlite, SQLiteWebhookStore
        init_sqlite()
        _store = SQLiteWebhookStore()
        logger.info("Storage backend initialized: SQLite")

    elif STORE_BACKEND == "dynamodb":
        # Future: uncomment when DynamoDB backend is implemented
        # from storage.dynamodb_backend import DynamoDBWebhookStore
        # _store = DynamoDBWebhookStore(table_name=DYNAMODB_WEBHOOK_TABLE)
        raise NotImplementedError(
            "DynamoDB backend not yet implemented. Set STORE_BACKEND=sqlite."
        )

    else:
        raise ValueError(f"Unknown STORE_BACKEND: {STORE_BACKEND}")


def get_webhook_store() -> WebhookStore:
    """Get the global webhook store instance.
    
    Returns:
        The initialized WebhookStore instance
        
    Raises:
        RuntimeError: If store not initialized (init_store not called)
    """
    if _store is None:
        raise RuntimeError("Store not initialized. Call init_store().")
    return _store


def close_store() -> None:
    """Close the storage backend.
    
    Called at shutdown to release resources.
    """
    global _store
    if STORE_BACKEND == "sqlite" and _store is not None:
        from storage.sqlite_backend import close_sqlite
        close_sqlite()
    _store = None
    logger.info("Storage backend closed")


# ============================================================================
# Directive Store
# ============================================================================

from config import (
    DIRECTIVE_STORE_ENABLED,
    DYNAMODB_DIRECTIVES_TABLE,
    AWS_REGION,
)

# Global directive store instance
_directive_store = None


def init_directive_store() -> None:
    """Initialize the directive store.
    
    Loads all active directives from DynamoDB and caches them.
    If DIRECTIVE_STORE_ENABLED is False, this is a no-op.
    """
    global _directive_store
    
    if not DIRECTIVE_STORE_ENABLED:
        logger.info("[DirectiveStore] Disabled via DIRECTIVE_STORE_ENABLED=false")
        return
    
    from storage.directive_store import DirectiveStore
    
    _directive_store = DirectiveStore(
        table_name=DYNAMODB_DIRECTIVES_TABLE,
        region=AWS_REGION
    )
    _directive_store.load()
    logger.info(
        f"[Startup] Loaded {len(_directive_store._cache)} active directives "
        f"from {DYNAMODB_DIRECTIVES_TABLE}"
    )


def get_directive_store():
    """Get the global directive store instance.
    
    Returns:
        The initialized DirectiveStore instance
        
    Raises:
        RuntimeError: If store not initialized or disabled
    """
    if _directive_store is None:
        if not DIRECTIVE_STORE_ENABLED:
            raise RuntimeError(
                "Directive store is disabled. Set DIRECTIVE_STORE_ENABLED=true."
            )
        raise RuntimeError(
            "Directive store not initialized. Call init_directive_store()."
        )
    return _directive_store
