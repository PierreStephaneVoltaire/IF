
from __future__ import annotations
import logging
from typing import Optional

from config import STORE_BACKEND
from storage.protocol import WebhookStore


logger = logging.getLogger(__name__)

_store: Optional[WebhookStore] = None


def init_store() -> None:

    global _store

    if STORE_BACKEND == "sqlite":
        from storage.sqlite_backend import init_sqlite, SQLiteWebhookStore
        init_sqlite()
        _store = SQLiteWebhookStore()
        logger.info("Storage backend initialized: SQLite")

    elif STORE_BACKEND == "dynamodb":
        raise NotImplementedError(
            "DynamoDB backend not yet implemented. Set STORE_BACKEND=sqlite."
        )

    else:
        raise ValueError(f"Unknown STORE_BACKEND: {STORE_BACKEND}")


def get_webhook_store() -> WebhookStore:

    if _store is None:
        raise RuntimeError("Store not initialized. Call init_store().")
    return _store


def close_store() -> None:

    global _store
    if STORE_BACKEND == "sqlite" and _store is not None:
        from storage.sqlite_backend import close_sqlite
        close_sqlite()
    _store = None
    logger.info("Storage backend closed")



from config import (
    DIRECTIVE_STORE_ENABLED,
    DYNAMODB_DIRECTIVES_TABLE,
    AWS_REGION,
)

_directive_store = None


def init_directive_store() -> None:

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

    if _directive_store is None:
        if not DIRECTIVE_STORE_ENABLED:
            raise RuntimeError(
                "Directive store is disabled. Set DIRECTIVE_STORE_ENABLED=true."
            )
        raise RuntimeError(
            "Directive store not initialized. Call init_directive_store()."
        )
    return _directive_store
