"""Memory module for RAG-backed persistent storage.

This module provides two storage systems:
1. UserFactStore - Structured facts about the operator (Phase2+)
2. MemoryStore - Legacy simple memory store (deprecated, kept for compatibility)
"""
# New user facts system (primary)
from .user_facts import (
    UserFact,
    FactCategory,
    FactSource,
    UserFactStore,
    get_user_fact_store,
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
    # New user facts system
    "UserFact",
    "FactCategory",
    "FactSource",
    "UserFactStore",
    "get_user_fact_store",
    # Legacy (deprecated)
    "MemoryStore",
    "MemoryEntry",
    "get_memory_store",
    "search_memories",
    "add_memory",
    "remove_memory",
]
