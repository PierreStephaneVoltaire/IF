"""Conversation state cache for routing decisions.

This module implements Step 4 of the routing pipeline:
- Caches routing decisions per conversation
- Stores anchor window for topic shift detection
- Implements reclassification logic via topic shift detection
- Handles social pattern detection (deprecated - now handled by topic shift)
"""
from __future__ import annotations
import re
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .scorer import AggregatedScores
from .decision import RoutingDecision


@dataclass
class ConversationState:
    """Cached state for a single conversation."""
    conversation_id: str
    active_preset: str
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
        initial_scores: AggregatedScores,
        initial_anchor_window: List[str]
    ) -> ConversationState:
        """Get existing state or create new one.
        
        Args:
            conversation_id: Unique conversation identifier
            initial_decision: Initial routing decision (for new conversations)
            initial_scores: Initial aggregated scores (for new conversations)
            initial_anchor_window: Initial message texts (for new conversations)
            
        Returns:
            ConversationState (existing or newly created)
        """
        if conversation_id in self._cache:
            return self._cache[conversation_id]
        
        # Create new state
        state = ConversationState(
            conversation_id=conversation_id,
            active_preset=initial_decision.selected_preset,
            anchor_window=initial_anchor_window,
            last_scores=initial_scores,
            last_decision=initial_decision
        )
        self._cache[conversation_id] = state
        return state
    
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
