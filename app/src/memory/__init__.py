"""Memory module for RAG-backed persistent storage.

This module provides two storage systems:
1. UserFactStore - Structured facts about the operator (LanceDB-backed, context-scoped)
2. MemoryStore - Legacy simple memory store (deprecated, kept for compatibility)

Context ID format for UserFactStore:
- OpenWebUI chat: openwebui_{chat_id}
- OpenWebUI channel: openwebui_{channel_id}
- Discord channel: discord_{channel_id}
"""
# New user facts system (primary) - LanceDB-backed
from .user_facts import (
    UserFact,
    FactCategory,
    FactSource,
    UserFactStore,
    get_user_fact_store,
    CapabilityGap,
    OpinionPair,
    Misconception,
    SessionReflection,
)

# LanceDB store internals
from .lancedb_store import (
    get_table,
    clear_table_cache,
    FACTS_BASE_PATH,
)

# Embedding utilities
from .embeddings import (
    embed,
    embed_batch,
    get_embedding_model,
    get_embedding_dimension,
)

# Legacy memory store (deprecated, but kept for backward compatibility)
try:
    from .store import (
        MemoryStore,
        MemoryEntry,
        get_memory_store,
        search_memories,
        add_memory,
        remove_memory,
    )
    _legacy_available = True
except ImportError:
    _legacy_available = False
    MemoryStore = None
    MemoryEntry = None
    get_memory_store = None
    search_memories = None
    add_memory = None
    remove_memory = None

__all__ = [
    # New user facts system (LanceDB-backed)
    "UserFact",
    "FactCategory",
    "FactSource",
    "UserFactStore",
    "get_user_fact_store",
    "CapabilityGap",
    "OpinionPair",
    "Misconception",
    "SessionReflection",
    # LanceDB internals
    "get_table",
    "clear_table_cache",
    "FACTS_BASE_PATH",
    # Embeddings
    "embed",
    "embed_batch",
    "get_embedding_model",
    "get_embedding_dimension",
    # Legacy (deprecated)
    "MemoryStore",
    "MemoryEntry",
    "get_memory_store",
    "search_memories",
    "add_memory",
    "remove_memory",
]
