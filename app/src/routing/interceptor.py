






import json
import logging
from typing import List, Dict, Any, Optional
import httpx

from config import (
    OPENWEBUI_TASK_MARKERS,
    SUGGESTION_MODEL,
)

logger = logging.getLogger(__name__)

class InterceptorResult:

    
    def __init__(
        self,
        is_suggestion_request: bool,
        response: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        self.is_suggestion_request = is_suggestion_request
        self.response = response
        self.error = error
    
    def should_bypass_routing(self) -> bool:

        return self.is_suggestion_request and self.response is not None

def detect_openwebui_task(messages: List[Dict[str, Any]]) -> bool:














    if not messages:
        return False
    
    last_message = messages[-1]
    content = last_message.get("content", "")
    
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(part.get("text", ""))
        content = " ".join(text_parts)
    
    if not isinstance(content, str):
        return False
    
    for marker in OPENWEBUI_TASK_MARKERS:
        if marker in content:
            return True
    
    return False

async def call_suggestion_model(
    messages: List[Dict[str, Any]],
    http_client: httpx.AsyncClient,
    model: str = SUGGESTION_MODEL,
    stream: bool = False
) -> Dict[str, Any]:













    from flow.codex_llm import call_codex_chat
    try:
        content = await call_codex_chat(model="gpt-5.6-luna", messages=messages, priority=10)
        return {"choices": [{"message": {"role": "assistant", "content": content}}]}
    except Exception as exc:
        return {"error": "Codex suggestion failed", "detail": str(exc)}

async def intercept_request(
    messages: List[Dict[str, Any]],
    http_client: httpx.AsyncClient,
    stream: bool = False
) -> InterceptorResult:












    is_task = detect_openwebui_task(messages)
    
    if not is_task:
        return InterceptorResult(is_suggestion_request=False)
    
    logger.info(f"Detected OpenWebUI task, calling {SUGGESTION_MODEL} directly")
    
    response = await call_suggestion_model(
        messages=messages,
        http_client=http_client,
        stream=stream
    )
    
    if "error" in response:
        return InterceptorResult(
            is_suggestion_request=True,
            error=response.get("detail", response.get("error"))
        )
    
    return InterceptorResult(
        is_suggestion_request=True,
        response=response
    )
