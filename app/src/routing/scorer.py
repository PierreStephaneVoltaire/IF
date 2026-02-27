"""Parallel scoring module for conversation classification.

This module implements Step 2 of the routing pipeline:
- Extracts last N messages from conversation
- Sends them to all scoring models in parallel
- Validates and aggregates scores
- Returns aggregated scores with crisis detection
"""
from __future__ import annotations
import asyncio
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

import httpx

from config import (
    SCORING_MODELS,
    MESSAGE_WINDOW,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
)
from presets.loader import PresetManager


@dataclass
class ScoringResult:
    """Result from a single scoring model."""
    model: str
    scores: Dict[str, float]  # preset_slug -> score, includes "crisis" key
    is_valid: bool = True
    error: Optional[str] = None
    top_preset: str = ""
    top_score: float = 0.0
    gap: float = 0.0  # Difference between top and second score
    
    def __post_init__(self):
        """Calculate top preset and gap after initialization."""
        if self.is_valid and self.scores:
            # Sort presets by score (excluding crisis)
            preset_scores = {
                k: v for k, v in self.scores.items() 
                if k != "crisis"
            }
            if preset_scores:
                sorted_scores = sorted(
                    preset_scores.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )
                self.top_preset = sorted_scores[0][0]
                self.top_score = sorted_scores[0][1]
                
                if len(sorted_scores) > 1:
                    self.gap = self.top_score - sorted_scores[1][1]
                else:
                    self.gap = self.top_score


@dataclass
class AggregatedScores:
    """Aggregated scores from all scoring models."""
    preset_scores: Dict[str, float]  # Final scores per preset
    crisis_score: float  # Max crisis score across models
    top_preset: str
    top_score: float
    second_preset: Optional[str] = None
    second_score: float = 0.0
    confidence_gap: float = 0.0
    winning_model: str = ""  # Model that provided the winning scores
    valid_models: int = 0
    total_models: int = 0


def build_scoring_prompt(
    preset_descriptions: Dict[str, str],
    messages: List[Dict[str, Any]]
) -> str:
    """Build the scoring prompt for conversation classification.
    
    Args:
        preset_descriptions: Map of preset slug -> description
        messages: Last N messages from conversation
        
    Returns:
        Formatted scoring prompt
    """
    # Format preset descriptions
    presets_text = "\n\n".join([
        f"**{slug}**: {desc}"
        for slug, desc in preset_descriptions.items()
    ])
    
    # Format conversation
    conversation_text = "\n\n".join([
        f"**{msg.get('role', 'unknown')}**: {msg.get('content', '')}"
        for msg in messages
    ])
    
    return f"""You are a conversation classifier. Given the following conversation and a set of preset descriptions, score how well the conversation matches each preset.

Return a JSON object where each key is the preset slug and the value is a confidence score from 0.0 to 1.0. Scores are independent — they do not need to sum to 1.

Additionally, include a "crisis" key scored 0.0 to 1.0 indicating whether the conversation contains signals of genuine distress, hopelessness, self-harm ideation, or mental health crisis. Score based on subtext and implication, not just explicit statements. A person in crisis rarely announces it directly.

Focus on the overall conversation topic but weight the most recent messages more heavily, especially the final message.

## PRESETS

{presets_text}

## CONVERSATION

{conversation_text}

Return ONLY valid JSON."""


def validate_scoring_response(
    response_text: str,
    expected_presets: set
) -> tuple[bool, Optional[Dict[str, float]], Optional[str]]:
    """Validate a scoring model's response.
    
    Args:
        response_text: Raw response from scoring model
        expected_presets: Set of expected preset slugs
        
    Returns:
        Tuple of (is_valid, parsed_scores, error_message)
    """
    try:
        # Parse JSON
        scores = json.loads(response_text)
        
        # Verify it's a dict
        if not isinstance(scores, dict):
            return False, None, "Response is not a JSON object"
        
        # Verify all preset slugs are present
        missing_presets = expected_presets - set(scores.keys())
        if missing_presets:
            return False, None, f"Missing presets: {missing_presets}"
        
        # Verify crisis key is present
        if "crisis" not in scores:
            return False, None, "Missing 'crisis' key"
        
        # Verify all values are floats between 0.0 and 1.0
        for key, value in scores.items():
            if not isinstance(value, (int, float)):
                return False, None, f"Value for '{key}' is not a number"
            if not (0.0 <= value <= 1.0):
                return False, None, f"Value for '{key}' out of range: {value}"
        
        # Convert all to float
        scores = {k: float(v) for k, v in scores.items()}
        
        return True, scores, None
        
    except json.JSONDecodeError as e:
        return False, None, f"JSON parse error: {e}"


async def score_with_model(
    model: str,
    prompt: str,
    http_client: httpx.AsyncClient,
    expected_presets: set
) -> ScoringResult:
    """Send scoring request to a single model.
    
    Args:
        model: Model identifier (e.g., "openrouter/mistral-nemo")
        prompt: Scoring prompt
        http_client: HTTP client for requests
        expected_presets: Set of expected preset slugs for validation
        
    Returns:
        ScoringResult with scores or error
    """
    try:
        response = await http_client.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,  # Low temperature for consistent scoring
                "max_tokens": 1000,
            },
            timeout=30.0,
        )
        
        if response.status_code != 200:
            return ScoringResult(
                model=model,
                scores={},
                is_valid=False,
                error=f"HTTP {response.status_code}: {response.text[:200]}"
            )
        
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        if not content:
            return ScoringResult(
                model=model,
                scores={},
                is_valid=False,
                error="Empty response from model"
            )
        
        # Validate the response
        is_valid, scores, error = validate_scoring_response(
            content, expected_presets
        )
        
        if not is_valid:
            return ScoringResult(
                model=model,
                scores={},
                is_valid=False,
                error=error
            )
        
        return ScoringResult(
            model=model,
            scores=scores,
            is_valid=True,
        )
        
    except Exception as e:
        return ScoringResult(
            model=model,
            scores={},
            is_valid=False,
            error=str(e)
        )


async def score_conversation(
    messages: List[Dict[str, Any]],
    preset_manager: PresetManager,
    http_client: httpx.AsyncClient
) -> AggregatedScores:
    """Score a conversation against all presets using parallel model calls.
    
    This implements Step 2 of the routing pipeline:
    1. Extract last MESSAGE_WINDOW messages
    2. Build scoring prompt with preset descriptions
    3. Send to all SCORING_MODELS in parallel
    4. Validate responses
    5. Aggregate scores using gap-based method
    6. Return aggregated scores with max crisis score
    
    Args:
        messages: Full conversation history
        preset_manager: Manager with loaded presets
        http_client: HTTP client for API calls
        
    Returns:
        AggregatedScores with final routing decision data
    """
    # Step 1: Extract last MESSAGE_WINDOW messages
    last_messages = messages[-MESSAGE_WINDOW:] if len(messages) > MESSAGE_WINDOW else messages
    
    if not last_messages:
        # No messages to score - return default
        return AggregatedScores(
            preset_scores={},
            crisis_score=0.0,
            top_preset="",
            top_score=0.0,
            valid_models=0,
            total_models=len(SCORING_MODELS)
        )
    
    # Step 2: Build scoring prompt
    preset_descriptions = preset_manager.get_preset_descriptions()
    expected_presets = set(preset_descriptions.keys())
    prompt = build_scoring_prompt(preset_descriptions, last_messages)
    
    # Step 3: Send to all scoring models in parallel
    scoring_tasks = [
        score_with_model(model, prompt, http_client, expected_presets)
        for model in SCORING_MODELS
    ]
    
    results = await asyncio.gather(*scoring_tasks, return_exceptions=True)
    
    # Step 4: Validate responses
    valid_results: List[ScoringResult] = []
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"[Scorer] Exception from {SCORING_MODELS[i]}: {result}")
            continue
        
        if result.is_valid:
            valid_results.append(result)
        else:
            print(f"[Scorer] Invalid result from {result.model}: {result.error}")
    
    # Step 5: Aggregate scores
    if not valid_results:
        # All models failed - return empty scores
        print("[Scorer] WARNING: All scoring models failed")
        return AggregatedScores(
            preset_scores={},
            crisis_score=0.0,
            top_preset="",
            top_score=0.0,
            valid_models=0,
            total_models=len(SCORING_MODELS)
        )
    
    # Find the model with the largest gap (most decisive)
    best_result = max(valid_results, key=lambda r: r.gap)
    
    # Aggregate crisis scores (take maximum)
    max_crisis = max(r.scores.get("crisis", 0.0) for r in valid_results)
    
    # Use the best model's scores
    preset_scores = {
        k: v for k, v in best_result.scores.items()
        if k != "crisis"
    }
    
    # Sort to find top and second
    sorted_presets = sorted(
        preset_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    top_preset = sorted_presets[0][0]
    top_score = sorted_presets[0][1]
    second_preset = sorted_presets[1][0] if len(sorted_presets) > 1 else None
    second_score = sorted_presets[1][1] if len(sorted_presets) > 1 else 0.0
    
    return AggregatedScores(
        preset_scores=preset_scores,
        crisis_score=max_crisis,
        top_preset=top_preset,
        top_score=top_score,
        second_preset=second_preset,
        second_score=second_score,
        confidence_gap=top_score - second_score,
        winning_model=best_result.model,
        valid_models=len(valid_results),
        total_models=len(SCORING_MODELS)
    )
