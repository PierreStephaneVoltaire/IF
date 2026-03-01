"""Conversation state cache for routing decisions.

This module implements Step 4 of the routing pipeline:
- Caches routing decisions per conversation
- Stores anchor window for topic shift detection
- Implements reclassification logic via topic shift detection
- Handles pinning to specific presets
- Persists to SQLite for survival across restarts
"""
from __future__ import annotations
import re
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .scorer import AggregatedScores
from .decision import RoutingDecision


logger = logging.getLogger(__name__)


@dataclass
class ConversationState:
    """Cached state for a single conversation."""
    cache_key: str  # chat_id or channel_id (renamed from conversation_id)
    active_preset: str
    pinned: bool = False
    pin_message_count: int = 0
    anchor_window: List[str] = field(default_factory=list)  # Message texts at last classification
    last_scores: Optional[AggregatedScores] = None
    last_decision: Optional[RoutingDecision] = None
    last_updated: datetime = field(default_factory=datetime.now)
    
    def update(
        self,
        decision: RoutingDecision,
        scores: AggregatedScores,
        anchor_window: List[str]
    ):
        """Update cached state with new routing decision.
        
        Args:
            decision: New routing decision
            scores: New aggregated scores
            anchor_window: Message texts at time of classification
        """
        self.active_preset = decision.selected_preset
        self.last_decision = decision
        self.last_scores = scores
        self.anchor_window = anchor_window
        self.last_updated = datetime.now()
    
    def should_reclassify(self, current_message: str) -> bool:
        """Determine if conversation should be reclassified.
        
        Args:
            current_message: The latest user message
            
        Returns:
            True if reclassification should occur
        """
        # Social patterns don't trigger reclassification
        if is_social_pattern(current_message):
            return False
        
        # If pinned, check pin lifecycle
        if self.pinned:
            return False  # Pinned presets don't auto-reclassify
        
        # Otherwise, let the routing pipeline decide
        return True


class ConversationCache:
    """In-memory cache for conversation routing states.
    
    Supports:
    - In-memory caching for fast access
    - Pinning to specific presets
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
    
    def pin(self, cache_key: str, preset: str) -> Optional[ConversationState]:
        """Pin a conversation to a specific preset.
        
        Args:
            cache_key: Conversation cache key
            preset: Preset slug to pin to
            
        Returns:
            Updated ConversationState or None if not found
        """
        state = self._cache.get(cache_key)
        if state:
            state.active_preset = preset
            state.pinned = True
            state.pin_message_count = 0
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
    
    def get_or_create(
        self,
        cache_key: str,
        initial_decision: RoutingDecision,
        initial_scores: AggregatedScores,
        initial_anchor_window: List[str]
    ) -> ConversationState:
        """Get existing state or create new one.
        
        Args:
            cache_key: Unique conversation identifier
            initial_decision: Initial routing decision (for new conversations)
            initial_scores: Initial aggregated scores (for new conversations)
            initial_anchor_window: Initial message texts (for new conversations)
            
        Returns:
            ConversationState (existing or newly created)
        """
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Create new state
        state = ConversationState(
            cache_key=cache_key,
            active_preset=initial_decision.selected_preset,
            anchor_window=initial_anchor_window,
            last_scores=initial_scores,
            last_decision=initial_decision
        )
        self._cache[cache_key] = state
        return state
    
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
                        active_preset=entry.active_preset,
                        pinned=bool(entry.pinned),
                        pin_message_count=entry.pin_message_count,
                        anchor_window=entry.get_anchor_window(),
                        last_updated=datetime.fromisoformat(
                            entry.last_updated.replace("Z", "+00:00")
                        ) if entry.last_updated else datetime.now(),
                    )
                    
                    # Parse last_scores if available
                    if entry.last_scores:
                        try:
                            scores_dict = entry.get_last_scores()
                            if scores_dict:
                                # Reconstruct AggregatedScores (simplified)
                                state.last_scores = scores_dict
                        except (json.JSONDecodeError, TypeError):
                            pass
                    
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
                entry.active_preset = state.active_preset
                entry.pinned = 1 if state.pinned else 0
                entry.pin_message_count = state.pin_message_count
                entry.set_anchor_window(state.anchor_window)
                if state.last_scores:
                    # Convert AggregatedScores to dict if needed
                    if hasattr(state.last_scores, 'to_dict'):
                        entry.set_last_scores(state.last_scores.to_dict())
                    else:
                        entry.set_last_scores(state.last_scores)
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


# Social pattern detection
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
    reclassification: greetings, acknowledgments, thanks, etc.
    
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
