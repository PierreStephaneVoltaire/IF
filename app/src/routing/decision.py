"""Decision logic for preset selection.

This module implements Step 3 of the routing pipeline:
- Crisis detection and routing
- Confident route selection
- Ambiguous route resolution
- Low confidence fallback
"""
from __future__ import annotations
from typing import Optional
from dataclasses import dataclass
import logging

from config import (
    CRISIS_THRESHOLD,
    CONFIDENCE_THRESHOLD,
    CONFIDENCE_GAP,
    MENTAL_HEALTH_PRESET,
)
from .scorer import AggregatedScores
from presets.loader import PresetManager


logger = logging.getLogger(__name__)


# Universal directives that apply to ALL preset categories
# These are always included in the applicable_directives list
UNIVERSAL_DIRECTIVES = ["0-1", "0-2", "0-3", "0-4", "2-14", "2-15", "2-16"]


@dataclass
class RoutingDecision:
    """Final routing decision with reasoning."""
    selected_preset: str
    crisis_triggered: bool = False
    confidence_level: str = "unknown"  # "crisis", "confident", "ambiguous", "fallback"
    top_score: float = 0.0
    second_score: float = 0.0
    gap: float = 0.0
    crisis_score: float = 0.0
    reason: str = ""
    log_message: str = ""


def select_preset(
    scores: AggregatedScores,
    preset_manager: PresetManager
) -> RoutingDecision:
    """Select the best preset based on aggregated scores.
    
    Implements Step 3 decision logic:
    1. Crisis check - route to mental health preset if crisis detected
    2. Confident route - high score with clear gap
    3. Ambiguous route - multiple high scores, pick most capable
    4. Low confidence fallback - route to most capable general preset
    
    Args:
        scores: Aggregated scores from Step 2
        preset_manager: Manager with preset capabilities
        
    Returns:
        RoutingDecision with selected preset and reasoning
    """
    # Handle edge case: no valid scores
    if not scores.preset_scores:
        # Fallback to most capable general preset
        default_preset = get_most_capable_preset(preset_manager)
        return RoutingDecision(
            selected_preset=default_preset,
            confidence_level="fallback",
            reason="No valid scores from scoring models",
            log_message="[Decision] WARNING: No valid scores, using fallback preset"
        )
    
    # Step 1: CRISIS CHECK
    if scores.crisis_score > CRISIS_THRESHOLD:
        logger.warning(
            f"Crisis detected: score={scores.crisis_score:.3f} "
            f"(threshold={CRISIS_THRESHOLD})"
        )
        return RoutingDecision(
            selected_preset=MENTAL_HEALTH_PRESET,
            crisis_triggered=True,
            confidence_level="crisis",
            crisis_score=scores.crisis_score,
            reason=f"Crisis score {scores.crisis_score:.3f} exceeds threshold {CRISIS_THRESHOLD}",
            log_message=(
                f"[Decision] CRISIS: score={scores.crisis_score:.3f} "
                f"→ routing to {MENTAL_HEALTH_PRESET}"
            )
        )
    
    # Step 2: CONFIDENT ROUTE
    if (scores.top_score > CONFIDENCE_THRESHOLD and 
        scores.confidence_gap > CONFIDENCE_GAP):
        return RoutingDecision(
            selected_preset=scores.top_preset,
            confidence_level="confident",
            top_score=scores.top_score,
            second_score=scores.second_score,
            gap=scores.confidence_gap,
            crisis_score=scores.crisis_score,
            reason=(
                f"High confidence: top={scores.top_score:.3f}, "
                f"gap={scores.confidence_gap:.3f}"
            ),
            log_message=(
                f"[Decision] CONFIDENT: {scores.top_preset} "
                f"(score={scores.top_score:.3f}, gap={scores.confidence_gap:.3f})"
            )
        )
    
    # Step 3: AMBIGUOUS ROUTE
    # Multiple presets score above threshold with small gap
    if scores.top_score > CONFIDENCE_THRESHOLD:
        # Get the most capable preset among top candidates
        candidates = [scores.top_preset]
        if scores.second_preset and scores.second_score > CONFIDENCE_THRESHOLD:
            candidates.append(scores.second_preset)
        
        # Select most capable among candidates
        selected = select_most_capable(candidates, preset_manager)
        
        return RoutingDecision(
            selected_preset=selected,
            confidence_level="ambiguous",
            top_score=scores.top_score,
            second_score=scores.second_score,
            gap=scores.confidence_gap,
            crisis_score=scores.crisis_score,
            reason=(
                f"Ambiguous: multiple presets above threshold, "
                f"selected most capable: {selected}"
            ),
            log_message=(
                f"[Decision] AMBIGUOUS: {selected} "
                f"(top={scores.top_preset}:{scores.top_score:.3f}, "
                f"second={scores.second_preset}:{scores.second_score:.3f})"
            )
        )
    
    # Step 4: LOW CONFIDENCE FALLBACK
    default_preset = get_most_capable_preset(preset_manager)
    
    logger.info(
        f"Low confidence routing: top_score={scores.top_score:.3f} "
        f"(threshold={CONFIDENCE_THRESHOLD}), using fallback"
    )
    
    return RoutingDecision(
        selected_preset=default_preset,
        confidence_level="fallback",
        top_score=scores.top_score,
        second_score=scores.second_score,
        gap=scores.confidence_gap,
        crisis_score=scores.crisis_score,
        reason=(
            f"Low confidence: top score {scores.top_score:.3f} "
            f"below threshold {CONFIDENCE_THRESHOLD}"
        ),
        log_message=(
            f"[Decision] FALLBACK: {default_preset} "
            f"(top={scores.top_preset}:{scores.top_score:.3f})"
        )
    )


def get_most_capable_preset(preset_manager: PresetManager) -> str:
    """Get the most capable general-purpose preset.
    
    This is used as a fallback when no clear routing decision can be made.
    The most capable preset is determined by model capability rankings.
    
    Args:
        preset_manager: Manager with preset information
        
    Returns:
        Slug of the most capable preset
    """
    # For now, return a hardcoded default
    # TODO: Implement capability-based selection from preset metadata
    # This could be based on:
    # - Model size/parameters
    # - Benchmark performance
    # - Cost (inverse - prefer more expensive = more capable)
    
    presets = preset_manager.get_all_presets()
    
    # Prefer these presets in order of capability (fallback order)
    capability_order = [
        "architecture",  # Claude 3.5 Sonnet - most capable
        "coding",        # Claude 3.5 Sonnet
        "reasoning",     # o1-preview
        "general",       # Default general-purpose
    ]
    
    for preset in capability_order:
        if preset in presets:
            return preset
    
    # If none of the preferred presets exist, return the first available
    if presets:
        return list(presets.keys())[0]
    
    # Ultimate fallback (should never happen if presets loaded correctly)
    return "general"


def select_most_capable(
    candidates: list[str],
    preset_manager: PresetManager
) -> str:
    """Select the most capable preset from a list of candidates.
    
    Args:
        candidates: List of preset slugs to choose from
        preset_manager: Manager with preset information
        
    Returns:
        Slug of the most capable preset from candidates
    """
    if len(candidates) == 1:
        return candidates[0]
    
    # For now, use a simple capability ranking
    # TODO: Implement proper capability scoring from preset metadata
    
    capability_ranking = {
        "architecture": 100,
        "coding": 95,
        "reasoning": 90,
        "general": 50,
        "social": 40,
        "creative": 35,
        "health": 30,
    }
    
    # Rank candidates by capability
    ranked = sorted(
        candidates,
        key=lambda p: capability_ranking.get(p, 0),
        reverse=True
    )
    
    return ranked[0]
