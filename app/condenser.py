"""Condenser module using OpenHands SDK for context window management.

This module wraps OpenHands' built-in condenser functionality to manage
conversation context when approaching token limits.
"""
from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from openhands.sdk import LLMSummarizingCondenser as Condenser, LLM

# Token threshold for triggering condensation
TOKEN_THRESHOLD = 100_000

# Target size after condensation
TARGET_TOKENS = 50_000

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
CONDENSER_MODEL = "moonshotai/kimi-k2.5"


@dataclass
class CondensationResult:
    """Result of a condensation operation."""
    condensed_messages: List[Dict[str, Any]]
    summary: str
    original_tokens: int
    condensed_tokens: int
    compression_ratio: float
    timestamp: str


def estimate_tokens(messages: List[Any]) -> int:
    """Estimate token count for a list of messages.
    
    Uses a simple heuristic: ~4 characters per token.
    Handles both dict messages and LangChain message objects.
    """
    total_chars = 0
    for msg in messages:
        # Handle LangChain message objects
        if hasattr(msg, 'content'):
            content = msg.content
        elif isinstance(msg, dict):
            content = msg.get("content", "")
        else:
            content = str(msg)
            
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    total_chars += len(part["text"])
                elif hasattr(part, 'text'):
                    total_chars += len(part.text)
        total_chars += 20  # overhead
    return int(total_chars * 0.25)


def create_condenser(
    model: str = CONDENSER_MODEL,
    token_threshold: int = TOKEN_THRESHOLD,
    target_tokens: int = TARGET_TOKENS,
    api_key: Optional[str] = None
) -> Condenser:
    """Create an OpenHands Condenser instance.
    
    Args:
        model: Model to use for condensation
        token_threshold: Token count to trigger condensation
        target_tokens: Target token count after condensation
        api_key: API key for the LLM provider
        
    Returns:
        Configured Condenser instance
    """
    llm = LLM(
        model=model,
        api_key=api_key or OPENROUTER_API_KEY,
    )
    
    condenser = Condenser(
        llm=llm,
        token_threshold=token_threshold,
        target_tokens=target_tokens,
    )
    
    return condenser


# Global condenser instance
_condenser: Optional[Condenser] = None


def get_condenser() -> Condenser:
    """Get or create the global condenser instance."""
    global _condenser
    if _condenser is None:
        _condenser = create_condenser()
    return _condenser


async def condense_conversation(
    messages: List[Dict[str, Any]],
    existing_summary: Optional[str] = None,
    target_tokens: int = TARGET_TOKENS
) -> CondensationResult:
    """Condense a conversation using OpenHands Condenser.
    
    Args:
        messages: List of conversation messages
        existing_summary: Previous summary to build upon
        target_tokens: Target token count after condensation
        
    Returns:
        CondensationResult with condensed messages and metadata
    """
    original_tokens = estimate_tokens(messages)
    
    # If below threshold, no condensation needed
    if original_tokens < TOKEN_THRESHOLD:
        return CondensationResult(
            condensed_messages=messages,
            summary=existing_summary or "",
            original_tokens=original_tokens,
            condensed_tokens=original_tokens,
            compression_ratio=1.0,
            timestamp=datetime.utcnow().isoformat()
        )
    
    print(f"[Condenser] Token count {original_tokens:,} exceeds threshold {TOKEN_THRESHOLD:,}")
    print(f"[Condenser] Starting condensation using OpenHands Condenser")
    
    # Get the condenser
    condenser = get_condenser()
    
    # Use OpenHands condenser
    # The condenser handles the summarization and message selection
    try:
        result = await condenser.condense(
            messages=messages,
            existing_summary=existing_summary,
        )
        
        condensed_messages = result.messages
        summary = result.summary
        condensed_tokens = estimate_tokens(condensed_messages)
        
    except Exception as e:
        print(f"[Condenser] OpenHands condenser error: {e}, using fallback")
        # Fallback: keep recent messages
        recent_count = min(len(messages), 10)
        condensed_messages = messages[-recent_count:]
        summary = existing_summary or "Conversation condensed due to length."
        condensed_tokens = estimate_tokens(condensed_messages)
    
    compression_ratio = condensed_tokens / original_tokens if original_tokens > 0 else 1.0
    
    print(f"[Condenser] Condensed {original_tokens:,} → {condensed_tokens:,} tokens ({compression_ratio:.1%})")
    
    return CondensationResult(
        condensed_messages=condensed_messages,
        summary=summary,
        original_tokens=original_tokens,
        condensed_tokens=condensed_tokens,
        compression_ratio=compression_ratio,
        timestamp=datetime.utcnow().isoformat()
    )


async def should_condense(messages: List[Dict[str, Any]]) -> bool:
    """Check if condensation should be triggered."""
    return estimate_tokens(messages) >= TOKEN_THRESHOLD


class ConversationCondenser:
    """Manages conversation condensation using OpenHands Condenser."""
    
    def __init__(
        self,
        token_threshold: int = TOKEN_THRESHOLD,
        target_tokens: int = TARGET_TOKENS,
        model: str = CONDENSER_MODEL
    ):
        self.token_threshold = token_threshold
        self.target_tokens = target_tokens
        self.model = model
        self.condenser = create_condenser(
            model=model,
            token_threshold=token_threshold,
            target_tokens=target_tokens
        )
        self.current_summary: Optional[str] = None
        self.last_condensation_tokens: int = 0
    
    async def process_messages(
        self,
        messages: List[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], bool]:
        """Process messages and condense if needed.
        
        Returns:
            Tuple of (processed_messages, was_condensed)
        """
        current_tokens = estimate_tokens(messages)
        
        if current_tokens < self.token_threshold:
            return messages, False
        
        # Don't condense too frequently
        if self.last_condensation_tokens > 0:
            if current_tokens < self.last_condensation_tokens * 1.2:
                return messages, False
        
        result = await condense_conversation(
            messages,
            existing_summary=self.current_summary,
            target_tokens=self.target_tokens
        )
        
        self.current_summary = result.summary
        self.last_condensation_tokens = result.condensed_tokens
        
        return result.condensed_messages, True
    
    def get_summary(self) -> Optional[str]:
        """Get the current conversation summary."""
        return self.current_summary
    
    def reset(self) -> None:
        """Reset the condenser state."""
        self.current_summary = None
        self.last_condensation_tokens = 0
