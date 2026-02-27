"""Request interceptor for OpenWebUI suggestion detection.

This module implements Step 1 of the routing pipeline:
- Detects OpenWebUI suggestion and title generation requests
- Bypasses the routing pipeline for these requests
- Calls the SUGGESTION_MODEL directly via OpenRouter
"""
import json
from typing import List, Dict, Any, Optional
import httpx

from config import (
    OPENWEBUI_TASK_MARKERS,
    SUGGESTION_MODEL,
    OPENROUTER_BASE_URL,
    OPENROUTER_HEADERS,
)


class InterceptorResult:
    """Result from the interceptor check."""
    
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
        """Check if routing should be bypassed."""
        return self.is_suggestion_request and self.response is not None


def detect_openwebui_task(messages: List[Dict[str, Any]]) -> bool:
    """Detect if the request is an OpenWebUI suggestion or title generation task.
    
    Detection heuristics:
    - The messages array contains a single message with content matching
      OpenWebUI's suggestion prompt patterns
    - The message array is very short (1-2 messages) and the content asks
      for title suggestions or conversation summaries
    
    Args:
        messages: List of message dictionaries with 'content' field
        
    Returns:
        True if this appears to be an OpenWebUI task, False otherwise
    """
    if not messages:
        return False
    
    # Check the last message content
    last_message = messages[-1]
    content = last_message.get("content", "")
    
    # Handle both string and list content formats
    if isinstance(content, list):
        # OpenAI format with content as list of objects
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(part.get("text", ""))
        content = " ".join(text_parts)
    
    if not isinstance(content, str):
        return False
    
    # Check for known OpenWebUI task markers
    for marker in OPENWEBUI_TASK_MARKERS:
        if marker in content:
            return True
    
    # Additional heuristics for short suggestion-like requests
    if len(messages) <= 2:
        # Check for common suggestion patterns
        suggestion_patterns = [
            "suggest",
            "title",
            "follow-up",
            "tags",
            "summarize",
        ]
        content_lower = content.lower()
        if any(pattern in content_lower for pattern in suggestion_patterns):
            # Additional check: these are usually very short prompts
            if len(content) < 500:  # Suggestion prompts are typically short
                return True
    
    return False


async def call_suggestion_model(
    messages: List[Dict[str, Any]],
    http_client: httpx.AsyncClient,
    model: str = SUGGESTION_MODEL,
    stream: bool = False
) -> Dict[str, Any]:
    """Call the suggestion model directly via OpenRouter.
    
    This bypasses the routing pipeline for fast, cheap suggestion generation.
    
    Args:
        messages: List of message dictionaries
        http_client: Async HTTP client for making requests
        model: Model to use for suggestions (default: SUGGESTION_MODEL)
        stream: Whether to stream the response
        
    Returns:
        OpenAI-compatible response dictionary
    """
    url = f"{OPENROUTER_BASE_URL}/chat/completions"
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    
    try:
        response = await http_client.post(
            url,
            headers=OPENROUTER_HEADERS,
            json=payload,
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text if e.response else str(e)
        return {
            "error": f"OpenRouter API error: {e.response.status_code}",
            "detail": error_detail
        }
    except Exception as e:
        return {
            "error": "Failed to call suggestion model",
            "detail": str(e)
        }


async def intercept_request(
    messages: List[Dict[str, Any]],
    http_client: httpx.AsyncClient,
    stream: bool = False
) -> InterceptorResult:
    """Intercept incoming requests and handle OpenWebUI tasks.
    
    This is the main entry point for Step 1 of the routing pipeline.
    
    Args:
        messages: List of message dictionaries from the request
        http_client: Async HTTP client for making API calls
        stream: Whether the original request was streaming
        
    Returns:
        InterceptorResult indicating whether to bypass routing
    """
    # Check if this is an OpenWebUI suggestion request
    is_task = detect_openwebui_task(messages)
    
    if not is_task:
        # Not a suggestion request, proceed to routing pipeline
        return InterceptorResult(is_suggestion_request=False)
    
    # This is a suggestion request - call model directly
    print(f"[Interceptor] Detected OpenWebUI task, calling {SUGGESTION_MODEL} directly")
    
    response = await call_suggestion_model(
        messages=messages,
        http_client=http_client,
        stream=stream
    )
    
    # Check for errors
    if "error" in response:
        return InterceptorResult(
            is_suggestion_request=True,
            error=response.get("detail", response.get("error"))
        )
    
    # Return successful response
    return InterceptorResult(
        is_suggestion_request=True,
        response=response
    )
