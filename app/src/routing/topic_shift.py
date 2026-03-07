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
from agent.prompts.loader import render_template


logger = logging.getLogger(__name__)


def should_check_shift(anchor_msgs: List[str], current_msgs: List[str]) -> bool:
    """Heuristic check to determine if topic shift detection is needed.
    
    Skip LLM call for obvious non-shifts (short messages, commands).
    Check keyword overlap to detect likely shifts.
    
    Args:
        anchor_msgs: Messages from the anchor window
        current_msgs: Current message window
        
    Returns:
        True if topic shift check should proceed, False to skip
    """
    latest = current_msgs[-1].strip() if current_msgs else ""

    # Short acknowledgments — never a topic shift
    if len(latest) < 15:
        return False

    # Command prefix — handled elsewhere
    if latest.startswith("/"):
        return False

    # Keyword overlap between anchor and current windows
    anchor_words = _extract_keywords(" ".join(anchor_msgs))
    current_words = _extract_keywords(" ".join(current_msgs))

    if not anchor_words or not current_words:
        return True  # Can't determine — let LLM decide

    overlap = len(anchor_words & current_words) / max(len(anchor_words), len(current_words))
    return overlap <= 0.4


def _extract_keywords(text: str) -> set:
    """Extract keywords using NLTK stopwords. Fallback to no filtering if unavailable."""
    try:
        from nltk.corpus import stopwords
        stop = set(stopwords.words("english"))
    except (ImportError, LookupError):
        stop = set()

    words = set(text.lower().split())
    filtered = {w for w in words if w not in stop and len(w) > 2}
    return filtered if filtered else words


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

    prompt = render_template(
        "topic_shift.j2",
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
