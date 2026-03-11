"""Context-aware preset tiering system.

This module implements tier-based model selection:
- Air tier (0): Fast, lightweight for simple tasks
- Standard tier (1): Balanced performance
- Heavy tier (2): Maximum capability for complex tasks

Tiers are selected based on context size, with automatic upgrades
when context approaches the current tier's limit.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

from config import (
    TIER_UPGRADE_THRESHOLD,
    TIER_AIR_LIMIT,
    TIER_STANDARD_LIMIT,
    TIER_HEAVY_LIMIT,
    TIER_AIR_PRESET,
    TIER_STANDARD_PRESET,
    TIER_HEAVY_PRESET,
)


logger = logging.getLogger(__name__)


@dataclass
class PresetTier:
    """Configuration for a single preset tier.

    Attributes:
        name: Human-readable tier name
        tier: Numeric tier (0=air, 1=standard, 2=heavy)
        preset: OpenRouter preset slug
        context_limit: Maximum context tokens before upgrade
    """
    name: str
    tier: int
    preset: str
    context_limit: int


# Tier definitions loaded from config
TIERS: List[PresetTier] = [
    PresetTier(
        name="air",
        tier=0,
        preset=TIER_AIR_PRESET,
        context_limit=TIER_AIR_LIMIT,
    ),
    PresetTier(
        name="standard",
        tier=1,
        preset=TIER_STANDARD_PRESET,
        context_limit=TIER_STANDARD_LIMIT,
    ),
    PresetTier(
        name="heavy",
        tier=2,
        preset=TIER_HEAVY_PRESET,
        context_limit=TIER_HEAVY_LIMIT,
    ),
]


def estimate_context_tokens(
    system_prompt: str,
    messages: List[dict],
    tool_overhead: int = 0
) -> int:
    """Estimate total context token count.

    Uses a simple heuristic of ~4 characters per token.

    Args:
        system_prompt: Full system prompt text
        messages: List of conversation messages
        tool_overhead: Additional tokens for tool definitions

    Returns:
        Estimated token count
    """
    total_chars = len(system_prompt)

    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            # Handle multi-part content (e.g., images, text blocks)
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    total_chars += len(part.get("text", ""))

    # Rough estimate: ~4 chars per token
    text_tokens = total_chars // 4

    # Add message overhead (~4 tokens per message for role, etc.)
    message_overhead = len(messages) * 4

    return text_tokens + message_overhead + tool_overhead


def check_tier(
    context_tokens: int,
    current_tier: int
) -> Tuple[bool, Optional[int]]:
    """Check if context requires tier adjustment.

    Args:
        context_tokens: Current context token estimate
        current_tier: Current tier number (0-2)

    Returns:
        Tuple of (try_condensation, upgrade_available):
        - try_condensation: True if context exceeds limit and condensation should be tried
        - upgrade_available: New tier if upgrade available, None otherwise
    """
    tier_config = get_tier(current_tier)
    if not tier_config:
        return False, None

    # Check if we're approaching the limit
    threshold_tokens = int(tier_config.context_limit * TIER_UPGRADE_THRESHOLD)

    if context_tokens >= tier_config.context_limit:
        # Over limit - try condensation first
        return True, None

    if context_tokens >= threshold_tokens:
        # Approaching limit - check for upgrade
        next_tier = get_next_tier(current_tier)
        if next_tier:
            logger.info(
                f"[Tiering] Context at {context_tokens} tokens "
                f"({context_tokens/tier_config.context_limit:.1%} of {tier_config.name} limit), "
                f"suggesting upgrade to {next_tier.name}"
            )
            return False, next_tier.tier

    return False, None


def get_tier(tier: int) -> Optional[PresetTier]:
    """Get tier configuration by tier number.

    Args:
        tier: Tier number (0-2)

    Returns:
        PresetTier if found, None otherwise
    """
    for t in TIERS:
        if t.tier == tier:
            return t
    return None


def get_preset_for_tier(tier: int) -> str:
    """Get the preset slug for a tier.

    Args:
        tier: Tier number (0-2)

    Returns:
        OpenRouter preset slug
    """
    tier_config = get_tier(tier)
    if tier_config:
        return tier_config.preset
    # Default to air tier if not found
    return TIER_AIR_PRESET


def get_next_tier(current: int) -> Optional[PresetTier]:
    """Get the next higher tier, if available.

    Args:
        current: Current tier number

    Returns:
        Next PresetTier if available, None if already at highest
    """
    for tier in TIERS:
        if tier.tier == current + 1:
            return tier
    return None


def get_tier_for_context(context_tokens: int) -> int:
    """Determine appropriate tier for a given context size.

    This finds the lowest tier that can accommodate the context.

    Args:
        context_tokens: Estimated context tokens

    Returns:
        Tier number (0-2)
    """
    for tier in TIERS:
        if context_tokens <= tier.context_limit:
            return tier.tier

    # If over even heavy limit, return heavy (will need condensation)
    return TIERS[-1].tier
