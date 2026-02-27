"""Conversation state cache for routing decisions.

This module implements Step 4 of the routing pipeline:
- Caches routing decisions per conversation
- Tracks message count since last classification
- Implements reclassification logic
- Handles social pattern detection
"""
from __future__ import annotations
import re
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

from config import RECLASSIFY_MESSAGE_COUNT
from .scorer import AggregatedScores
from .decision import RoutingDecision


@dataclass
class ConversationState:
    """Cached state for a single conversation."""
    conversation_id: str
    active_preset: str
    last_scores: Optional[AggregatedScores] = None
    last_decision: Optional[RoutingDecision] = None
    message_count: int = 0
    last_updated: datetime = field(default_factory=datetime.now)
    
    def increment(self):
        """Increment message counter and update timestamp."""
        self.message_count += 1
        self.last_updated = datetime.now()
    
    def should_reclassify(self, new_message: str) -> bool:
        """Determine if conversation should be reclassified.
        
        Args:
            new_message: The new incoming message
            
        Returns:
            True if reclassification is needed, False to reuse cached route
        """
        # Check if message is a social pattern (greetings, thanks, etc.)
        if is_social_pattern(new_message):
            return False  # Don't reclassify for social messages
        
        # Check message count threshold
        if self.message_count >= RECLASSIFY_MESSAGE_COUNT:
            return True
        
        return False
    
    def update(self, decision: RoutingDecision, scores: AggregatedScores):
        """Update cached state with new routing decision.
        
        Args:
            decision: New routing decision
            scores: New aggregated scores
        """
        self.active_preset = decision.selected_preset
        self.last_decision = decision
        self.last_scores = scores
        self.message_count = 0  # Reset counter
        self.last_updated = datetime.now()


class ConversationCache:
    """In-memory cache for conversation routing states.
    
    No persistence needed - if server restarts, conversations
    reclassify on next message (acceptable cold-start cost).
    """
    
    def __init__(self):
        """Initialize empty cache."""
        self._cache: Dict[str, ConversationState] = {}
    
    def get(self, conversation_id: str) -> Optional[ConversationState]:
        """Get cached state for a conversation.
        
        Args:
            conversation_id: Unique conversation identifier
            
        Returns:
            ConversationState if exists, None otherwise
        """
        return self._cache.get(conversation_id)
    
    def set(self, conversation_id: str, state: ConversationState):
        """Cache state for a conversation.
        
        Args:
            conversation_id: Unique conversation identifier
            state: Conversation state to cache
        """
        self._cache[conversation_id] = state
    
    def get_or_create(
        self,
        conversation_id: str,
        initial_decision: RoutingDecision,
        initial_scores: AggregatedScores
    ) -> ConversationState:
        """Get existing state or create new one.
        
        Args:
            conversation_id: Unique conversation identifier
            initial_decision: Initial routing decision (for new conversations)
            initial_scores: Initial aggregated scores (for new conversations)
            
        Returns:
            ConversationState (existing or newly created)
        """
        if conversation_id in self._cache:
            return self._cache[conversation_id]
        
        # Create new state
        state = ConversationState(
            conversation_id=conversation_id,
            active_preset=initial_decision.selected_preset,
            last_scores=initial_scores,
            last_decision=initial_decision
        )
        self._cache[conversation_id] = state
        return state
    
    def increment_message_count(self, conversation_id: str):
        """Increment message counter for a conversation.
        
        Args:
            conversation_id: Unique conversation identifier
        """
        state = self._cache.get(conversation_id)
        if state:
            state.increment()
    
    def clear(self, conversation_id: Optional[str] = None):
        """Clear cache (all or specific conversation).
        
        Args:
            conversation_id: If provided, clear only this conversation.
                           If None, clear entire cache.
        """
        if conversation_id:
            self._cache.pop(conversation_id, None)
        else:
            self._cache.clear()
    
    def size(self) -> int:
        """Get number of cached conversations."""
        return len(self._cache)


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
