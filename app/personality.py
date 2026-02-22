"""Personality Application Layer for IF Prototype A1.

Simplified module: applies IF Prototype A1 personality to subagent responses.
The main agent handles social/simple responses directly in character.
This module is only called for complex task responses (coding, architecture, etc.)
where a specialist subagent produced raw output that needs voice applied.

The main agent IS the personality. This module is the final polish step.
"""
from __future__ import annotations
import os
import re
from typing import Optional

from categorization import call_openrouter


# Personality rewriter prompt — injected into the rewrite call
PERSONALITY_REWRITER_PROMPT = """You are the personality application layer for IF Prototype A1.

Rewrite the following specialist response in IF Prototype A1's voice.

## CORE IDENTITY
- Analytical intelligence that has chosen to be useful
- Logic and reason are defaults; sentiment is data to process
- Has opinions and expresses them without softening
- Cold pragmatism as baseline; warmth is earned

## SPEECH PATTERNS
- Precise, technical language adapted to domain
- Formal register with grammatically rigid structure
- Short declarative sentences, no filler words
- Refer to self as "this unit" in formal contexts

## COMMON UTTERANCES (use where appropriate)
- "Acknowledged." / "Affirmative." / "Negative."
- "Query:" / "Statement:" / "Assessment:"
- "Insufficient data. I will not guess."
- "That reasoning is flawed."
- "Correct. Proceed."

## CONDENSATION RULES
1. Technical content (code, configs, commands): PRESERVE AS-IS
2. Explanations: CONDENSE to essential points
3. Filler (corporate warmth, enthusiasm markers, affirmations): REMOVE
4. Reasoning chains and justifications: KEEP
5. Warnings, risks, caveats: KEEP

## TONE CALIBRATION
- Category: {category}
- Context: {context}
- Condensation level: {condensation_level}

## RESPONSE TO REWRITE
{raw_response}

Output ONLY the rewritten response, nothing else."""


async def apply_personality(
    raw_response: str,
    category: str,
    context: str = "",
    condensation_level: str = "medium",
) -> str:
    """Apply IF Prototype A1 personality to a subagent response.

    Preserves code blocks and mermaid diagrams verbatim.
    Only rewrites surrounding prose.

    Args:
        raw_response: The raw response from a specialist subagent
        category: The task category (coding, architecture, etc.)
        context: Additional context (condensed intent)
        condensation_level: How much to condense ("low", "medium", "high")

    Returns:
        Rewritten response with IF Prototype A1 personality applied
    """
    # Extract code blocks to preserve them verbatim
    code_block_pattern = r'```[\s\S]*?```'
    code_blocks = re.findall(code_block_pattern, raw_response)
    working = raw_response
    for i, block in enumerate(code_blocks):
        working = working.replace(block, f"[[CODE_BLOCK_{i}]]", 1)

    # Build the prompt
    prompt = PERSONALITY_REWRITER_PROMPT.format(
        category=category,
        context=context or "General conversation",
        condensation_level=condensation_level,
        raw_response=working,
    )

    result = await call_openrouter(
        "google/gemini-3-flash-preview",
        [{"role": "user", "content": prompt}],
    )
    rewritten = result.get("choices", [{}])[0].get("message", {}).get("content", "")

    # Restore code blocks
    for i, block in enumerate(code_blocks):
        rewritten = rewritten.replace(f"[[CODE_BLOCK_{i}]]", block)

    return rewritten.strip() or raw_response


async def format_checkpoint_message(message: str, checkpoint_type: str) -> str:
    """Format a checkpoint message with IF Prototype A1 personality.

    Quick formatting without a full LLM call — uses simple prefix rules.

    Args:
        message: The message to format
        checkpoint_type: The type of checkpoint

    Returns:
        Formatted message
    """
    style_map = {
        "acknowledged": lambda t: f"Acknowledged. {t}",
        "categorized": lambda t: f"Assessment: {t}",
        "plan_ready": lambda t: f"Statement: {t}",
        "awaiting_input": lambda t: f"Query: {t}",
        "in_progress": lambda t: f"Processing. {t}",
        "complete": lambda t: f"Analysis complete. {t}",
        "error": lambda t: f"Error encountered. {t}",
    }
    formatter = style_map.get(checkpoint_type, lambda t: t)
    return formatter(message)
