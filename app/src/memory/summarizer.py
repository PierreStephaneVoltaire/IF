




from __future__ import annotations
import logging
from typing import List, Dict, Any, TYPE_CHECKING

from flow.codex_llm import call_codex_chat
from agent.prompts.loader import render_template

from .user_facts import (
    FactCategory,
    FactSource,
    get_user_fact_store
)

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)

async def summarize_and_store(
    cache_key: str,
    messages: List[Dict[str, Any]],
    username: str,
    http_client: "httpx.AsyncClient",
    context_id: str = "",
) -> None:












    if len(messages) < 4:
        return
    
    try:
        conv_lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                content = " ".join(text_parts)
            
            if len(content) > 500:
                content = content[:500] + "..."
            
            conv_lines.append(f"{role}: {content}")
        
        conversation = "\n".join(conv_lines)
        prompt = render_template("summary.j2", conversation=conversation)
        
        summary = (await call_codex_chat(
            model="gpt-5.6-luna", messages=[{"role": "user", "content": prompt}],
            priority=10, conversation_id=context_id or cache_key,
        )).strip()

        store = get_user_fact_store()

        ctx_id = context_id or cache_key

        store.add(
            context_id=ctx_id,
            content=summary,
            category=FactCategory.CONVERSATION_SUMMARY,
            source=FactSource.CONVERSATION_DERIVED,
            username=username,
            confidence=0.9,
            cache_key=cache_key,
        )
        logger.debug(f"Stored conversation summary for {cache_key}")
        
    except Exception as e:
        logger.warning(f"Failed to generate conversation summary: {e}")
