"""Topic shift detection using LLM.

This module detects whether the conversation topic has shifted enough
to warrant reclassification. Uses a fast cheap LLM via OpenRouter —
same infrastructure as scoring.

Only called when the routing cache is WARM (preset already assigned).
Cold cache always runs the full scoring pipeline.
"""
from __future__ import annotations
import logging
from typing import List

import httpx

from config import (
    TOPIC_SHIFT_MODEL,
    OPENROUTER_API_KEY,
    LLM_BASE_URL,
)


logger = logging.getLogger(__name__)


TOPIC_SHIFT_PROMPT = """You are a conversation topic classifier. Your ONLY job is to determine whether the conversation topic has SIGNIFICANTLY changed.

## PREVIOUS CONVERSATION CONTEXT (used to select the current specialist):
{anchor_messages}

## NEW MESSAGES (most recent):
{current_messages}

## RULES:
- A topic shift means the user is now asking about something fundamentally different (e.g., coding → finance, architecture → health, debugging Python → discussing ETF performance).
- NOT a shift: continuing the same topic with follow-ups, clarifications, or acknowledgments.
- NOT a shift: social noise mid-conversation ("thanks", "ok", "got it", "nice", "lol").
- NOT a shift: moving between sub-topics within the same domain (Python async → Python decorators, Terraform → CloudFormation).
- IS a shift: moving between major domains (coding → powerlifting, architecture → mental health, finance → DevOps).
- When in doubt, answer false. Unnecessary reclassification is worse than one stale turn.

Respond with ONLY the word "true" or "false". Nothing else."""


async def topic_has_shifted(
    anchor_messages: List[str],
    current_messages: List[str],
    http_client: httpx.AsyncClient,
) -> bool:
    """Ask a fast LLM whether the conversation topic has significantly changed.

    Args:
        anchor_messages: The MESSAGE_WINDOW texts from the last classification.
        current_messages: The current MESSAGE_WINDOW texts.
        http_client: Shared async HTTP client (reuse from app state).

    Returns:
        True if topic has shifted. False if same topic or on failure (safe default).
    """
    anchor_block = "\n".join(
        f"- {msg}" for msg in anchor_messages
    )
    current_block = "\n".join(
        f"- {msg}" for msg in current_messages
    )

    prompt = TOPIC_SHIFT_PROMPT.format(
        anchor_messages=anchor_block,
        current_messages=current_block,
    )

    try:
        resp = await http_client.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": TOPIC_SHIFT_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 5,
                "temperature": 0.0,
            },
            timeout=5.0,  # Hard timeout — if it takes longer, use cache
        )
        resp.raise_for_status()
        answer = (
            resp.json()["choices"][0]["message"]["content"]
            .strip()
            .lower()
        )
        shifted = answer.startswith("true")
        logger.debug(
            f"Topic shift check: {answer} (shifted={shifted})"
        )
        return shifted

    except Exception as e:
        # On ANY failure: default to no shift (use cached preset).
        # Worst case: one stale turn. Next message retries.
        logger.warning(f"Topic shift check failed, using cache: {e}")
        return False
