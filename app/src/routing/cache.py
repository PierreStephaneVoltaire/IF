"""Conversation state cache for tier tracking.

This module implements tier-based state tracking:
- Tracks current tier (0=air, 1=standard, 2=heavy)
- Tracks context token estimates
- Handles pinning to specific tiers
- Supports pondering mode
- Persists to SQLite for survival across restarts
"""
from __future__ import annotations
import re
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone


logger = logging.getLogger(__name__)


@dataclass
class ConversationState:
    """Cached state for a single conversation.

    Tracks tier progression and context management.
    """
    cache_key: str  # chat_id or channel_id
    current_tier: int = 0  # 0=air, 1=standard, 2=heavy
    context_tokens: int = 0
    condensation_count: int = 0
    pinned: bool = False
    pinned_tier: Optional[int] = None  # Set when pinned to specific tier
    pondering: bool = False
    last_updated: datetime = field(default_factory=datetime.now)


class ConversationCache:
    """In-memory cache for conversation tier states.

    Supports:
    - In-memory caching for fast access
    - Pinning to specific tiers
    - Eviction for /end_convo command
    - SQLite persistence for survival across restarts
    """

    def __init__(self):
        """Initialize empty cache."""
        self._cache: Dict[str, ConversationState] = {}

    def get(self, cache_key: str) -> Optional[ConversationState]:
        """Get cached state for a conversation.

        Args:
            cache_key: Unique conversation identifier (chat_id or channel_id)

        Returns:
            ConversationState if exists, None otherwise
        """
        return self._cache.get(cache_key)

    def set(self, cache_key: str, state: ConversationState):
        """Cache state for a conversation.

        Args:
            cache_key: Unique conversation identifier
            state: Conversation state to cache
        """
        self._cache[cache_key] = state

    def get_or_create(self, cache_key: str) -> ConversationState:
        """Get existing state or create new one.

        Args:
            cache_key: Unique conversation identifier

        Returns:
            ConversationState (existing or newly created)
        """
        if cache_key in self._cache:
            return self._cache[cache_key]

        state = ConversationState(cache_key=cache_key)
        self._cache[cache_key] = state
        return state

    def pin(self, cache_key: str, tier: Optional[int] = None) -> Optional[ConversationState]:
        """Pin a conversation to a specific tier.

        Args:
            cache_key: Conversation cache key
            tier: Tier to pin to (optional, defaults to current tier)

        Returns:
            Updated ConversationState or None if not found
        """
        state = self._cache.get(cache_key)
        if state:
            state.pinned = True
            state.pinned_tier = tier if tier is not None else state.current_tier
            state.last_updated = datetime.now()
        return state

    def set_pondering(self, cache_key: str, enabled: bool = True) -> Optional[ConversationState]:
        """Enable or disable pondering mode.

        Args:
            cache_key: Conversation cache key
            enabled: True to enable pondering, False to disable

        Returns:
            Updated ConversationState or None if not found
        """
        state = self._cache.get(cache_key)
        if state:
            state.pondering = enabled
            state.last_updated = datetime.now()
        return state

    def evict(self, cache_key: str) -> bool:
        """Evict a conversation from the cache.

        Args:
            cache_key: Conversation cache key

        Returns:
            True if entry was evicted, False if not found
        """
        if cache_key in self._cache:
            del self._cache[cache_key]
            return True
        return False

    def clear(self, cache_key: Optional[str] = None):
        """Clear cache (all or specific conversation).

        Args:
            cache_key: If provided, clear only this conversation.
                       If None, clear entire cache.
        """
        if cache_key:
            self._cache.pop(cache_key, None)
        else:
            self._cache.clear()

    def size(self) -> int:
        """Get number of cached conversations."""
        return len(self._cache)

    # --- Persistence methods ---

    async def load_from_storage(self, storage_backend) -> int:
        """Load cache entries from SQLite storage.

        Called on startup to warm the cache.

        Args:
            storage_backend: The storage backend with SQLite session

        Returns:
            Number of entries loaded
        """
        try:
            from storage.models import RoutingCacheEntry

            with storage_backend.get_session() as session:
                entries = session.query(RoutingCacheEntry).all()
                loaded = 0

                for entry in entries:
                    # Skip expired entries
                    if entry.is_expired():
                        session.delete(entry)
                        continue

                    # Convert to ConversationState
                    state = ConversationState(
                        cache_key=entry.cache_key,
                        current_tier=entry.current_tier or 0,
                        context_tokens=entry.context_tokens or 0,
                        condensation_count=entry.condensation_count or 1,
                        pinned=bool(entry.pinned),
                        pinned_tier=entry.pinned_tier,
                        pondering=bool(entry.pondering) if hasattr(entry, 'pondering') else False,
                        last_updated=datetime.fromisoformat(
                            entry.last_updated.replace("Z", "+00:00")
                        ) if entry.last_updated else datetime.now(),
                    )

                    self._cache[entry.cache_key] = state
                    loaded += 1

                session.commit()
                logger.info(f"[Cache] Loaded {loaded} entries from storage")
                return loaded

        except Exception as e:
            logger.warning(f"[Cache] Failed to load from storage: {e}")
            return 0

    async def persist_entry(self, cache_key: str, storage_backend) -> bool:
        """Persist a single cache entry to SQLite.

        Args:
            cache_key: The cache key to persist
            storage_backend: The storage backend with SQLite session

        Returns:
            True if persisted successfully
        """
        state = self._cache.get(cache_key)
        if not state:
            return False

        try:
            from storage.models import RoutingCacheEntry

            with storage_backend.get_session() as session:
                # Find existing or create new
                entry = session.query(RoutingCacheEntry).filter(
                    RoutingCacheEntry.cache_key == cache_key
                ).first()

                if not entry:
                    entry = RoutingCacheEntry(cache_key=cache_key)
                    session.add(entry)

                # Update fields
                entry.current_tier = state.current_tier
                entry.context_tokens = state.context_tokens
                entry.condensation_count = state.condensation_count
                entry.pinned = 1 if state.pinned else 0
                entry.pinned_tier = state.pinned_tier
                if hasattr(entry, 'pondering'):
                    entry.pondering = 1 if state.pondering else 0
                entry.touch()

                session.commit()
                return True

        except Exception as e:
            logger.warning(f"[Cache] Failed to persist entry {cache_key}: {e}")
            return False

    async def persist_eviction(self, cache_key: str, storage_backend) -> bool:
        """Remove a cache entry from SQLite.

        Args:
            cache_key: The cache key to remove
            storage_backend: The storage backend with SQLite session

        Returns:
            True if removed successfully
        """
        try:
            from storage.models import RoutingCacheEntry

            with storage_backend.get_session() as session:
                entry = session.query(RoutingCacheEntry).filter(
                    RoutingCacheEntry.cache_key == cache_key
                ).first()

                if entry:
                    session.delete(entry)
                    session.commit()

                return True

        except Exception as e:
            logger.warning(f"[Cache] Failed to persist eviction {cache_key}: {e}")
            return False


# Social pattern detection (kept for message filtering)
SOCIAL_PATTERNS = [
    r'^thanks?$',
    r'^thank you$',
    r'^got it$',
    r'^ok$',
    r'^okay$',
    r'^sure$',
    r'^will do$',
    r'^sounds good$',
    r'^perfect$',
    r'^great$',
    r'^awesome$',
    r'^excellent$',
    r'^hi$',
    r'^hello$',
    r'^hey$',
    r'^good morning$',
    r'^good afternoon$',
    r'^good evening$',
    r'^bye$',
    r'^goodbye$',
    r'^see you$',
    r'^later$',
    r'^yes$',
    r'^no$',
    r'^yep$',
    r'^nope$',
    r'^right$',
    r'^correct$',
    r'^exactly$',
    r'^agreed$',
    r'^understood$',
    r'^gotcha$',
    r'^cool$',
    r'^nice$',
    r'^sweet$',
    r'^alright$',
    r'^all right$',
    r'^roger$',
    r'^copy$',
    r'^ack$',
]


def is_social_pattern(message: str) -> bool:
    """Check if message matches a social pattern.

    Social patterns are short messages that shouldn't trigger
    tier changes: greetings, acknowledgments, thanks, etc.

    Args:
        message: Message content to check

    Returns:
        True if message is a social pattern, False otherwise
    """
    # Normalize message
    normalized = message.strip().lower()

    # Check length - social patterns are short
    if len(normalized) > 20:
        return False

    # Check against patterns
    for pattern in SOCIAL_PATTERNS:
        if re.match(pattern, normalized):
            return True

    return False


# Global cache instance
_cache: Optional[ConversationCache] = None


def get_cache() -> ConversationCache:
    """Get the global conversation cache instance.

    Returns:
        ConversationCache singleton
    """
    global _cache
    if _cache is None:
        _cache = ConversationCache()
    return _cache
