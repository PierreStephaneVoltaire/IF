"""Chat completions endpoint for OpenAI compatibility.

POST /v1/chat/completions - Handle chat completions with intelligent routing.

This module provides both:
1. HTTP endpoint for OpenAI-compatible API
2. Internal pipeline function for channel integrations
"""
from __future__ import annotations
import uuid
import hashlib
import logging
from typing import TYPE_CHECKING, Dict, List, Any, Optional, Tuple

from fastapi import APIRouter, HTTPException, Request

from .schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatCompletionMessage,
)
from routing.interceptor import intercept_request
from routing.scorer import score_conversation
from routing.decision import select_preset
from routing.cache import get_cache
from presets.loader import get_preset_manager
from agent.session import get_or_create_session, execute_agent

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)

router = APIRouter()


def extract_conversation_id(messages: list) -> str:
    """Extract or generate a conversation ID from messages.
    
    In a full implementation, this would extract from metadata or headers.
    For now, generates a hash of the first message content.
    
    Args:
        messages: List of message dicts
        
    Returns:
        Conversation ID string
    """
    if not messages:
        return "default"
    
    # Use hash of first message content as conversation ID
    first_msg = messages[0]
    content = first_msg.get("content", "")
    
    # Handle content that might be a string or list of content parts
    if isinstance(content, list):
        # Extract text from content parts
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(part.get("text", ""))
            elif isinstance(part, str):
                text_parts.append(part)
        content = " ".join(text_parts)
    
    # Simple hash for conversation ID
    content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
    
    return f"conv-{content_hash}"


async def process_chat_completion_internal(
    request_data: Dict[str, Any],
    http_client: "httpx.AsyncClient",
    conversation_id: Optional[str] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Core pipeline for processing chat completions.
    
    This is the internal function that handles:
    1. Request Interception (OpenWebUI tasks)
    2. Parallel Scoring (preset selection)
    3. Decision Logic (best preset)
    4. Conversation State Cache (routing decisions)
    5. Agent Execution (run with selected preset)
    
    Used by:
    - POST /v1/chat/completions (HTTP clients)
    - Channel dispatcher (Discord, OpenWebUI)
    
    Args:
        request_data: Dict matching ChatCompletionRequest shape.
                      Must include 'messages'. Can include '_conversation_id'.
        http_client: Shared async HTTP client for API calls
        conversation_id: Optional conversation ID (extracted from messages if not provided)
        
    Returns:
        Tuple of (response_text, attachments) where attachments is a list of dicts
        with keys: filename, content_type, url, local_path.
        
    Raises:
        Exception: If processing fails at any stage
    """
    messages = request_data.get("messages", [])
    stream = request_data.get("stream", False)
    
    # Extract or use provided conversation ID
    if not conversation_id:
        conversation_id = request_data.get(
            "_conversation_id",
            extract_conversation_id(messages)
        )
    
    # Step 1: Request Interception
    # Check if this is an OpenWebUI suggestion/title generation request
    interceptor_result = await intercept_request(
        messages=messages,
        http_client=http_client,
        stream=stream
    )
    
    # If interceptor handled the request, return simple response
    if interceptor_result.should_bypass_routing():
        if interceptor_result.error:
            raise Exception(f"Interceptor error: {interceptor_result.error}")
        # Extract content from interceptor response
        response = interceptor_result.response
        if isinstance(response, dict):
            choices = response.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                return content, []
        return str(response), []
    
    # Get preset manager and conversation cache
    preset_manager = get_preset_manager()
    cache = get_cache()
    
    # Get the last user message for cache checking
    last_user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                last_user_message = content
            elif isinstance(content, list):
                # Extract text from content parts
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                last_user_message = " ".join(text_parts)
            break
    
    # Step 4: Check conversation cache
    cached_state = cache.get(conversation_id)
    selected_preset = None
    
    if cached_state:
        # Increment message counter
        cache.increment_message_count(conversation_id)
        
        # Check if we should reclassify
        should_reclassify = cached_state.should_reclassify(last_user_message)
        
        if not should_reclassify:
            # Reuse cached route
            logger.info(f"[Cache] Reusing cached preset: {cached_state.active_preset}")
            selected_preset = cached_state.active_preset
    
    # Step 2: Parallel Scoring (if no cached preset or reclassification needed)
    if selected_preset is None:
        scores = await score_conversation(
            messages=messages,
            preset_manager=preset_manager,
            http_client=http_client
        )
        
        # Step 3: Decision Logic
        decision = select_preset(
            scores=scores,
            preset_manager=preset_manager
        )
        
        # Log the routing decision
        logger.info(decision.log_message)
        selected_preset = decision.selected_preset
        
        # Step 4: Update conversation cache
        if cached_state:
            cached_state.update(decision, scores)
            logger.info(f"[Cache] Updated preset: {decision.selected_preset}")
        else:
            from routing.cache import ConversationState
            new_state = ConversationState(
                conversation_id=conversation_id,
                active_preset=decision.selected_preset,
                last_scores=scores,
                last_decision=decision
            )
            cache.set(conversation_id, new_state)
            logger.info(f"[Cache] Created new state with preset: {decision.selected_preset}")
    
    # Step 5: Agent Execution
    session = get_or_create_session(
        conversation_id=conversation_id,
        preset_slug=selected_preset,
        preset_manager=preset_manager
    )
    
    agent_response = await execute_agent(
        session=session,
        messages=messages,
        http_client=http_client,
        stream=stream
    )
    
    # Build attachments list
    attachments = []
    for att_path in agent_response.attachments:
        attachments.append({
            "filename": att_path,
            "url": f"/files/sandbox/{conversation_id}/{att_path}",
            "local_path": att_path,
            "content_type": "application/octet-stream",
        })
    
    return agent_response.content, attachments


@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    raw_request: Request
):
    """Handle chat completions with intelligent routing.
    
    HTTP endpoint that delegates to the core pipeline.
    
    Args:
        request: Chat completion request
        raw_request: Raw FastAPI request object
        
    Returns:
        Chat completion response
        
    Raises:
        HTTPException: If request validation fails or processing errors occur
    """
    # Validate model parameter
    if request.model != "if-prototype":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model '{request.model}'. Only 'if-prototype' model is supported."
        )
    
    # Get shared HTTP client from app state
    http_client = raw_request.app.state.http_client
    
    # Convert request to dict format
    request_data = request.model_dump(exclude_none=True)
    
    try:
        response_text, attachments = await process_chat_completion_internal(
            request_data=request_data,
            http_client=http_client,
        )
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    
    # Return OpenAI-compatible response
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
        model="if-prototype",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant",
                    content=response_text
                ),
                finish_reason="stop"
            )
        ]
    )


@router.post("/api/v1/chat/completions")
async def chat_completions_alias(
    request: ChatCompletionRequest,
    raw_request: Request
):
    """Alias for /v1/chat/completions (OpenWebUI compatibility).
    
    OpenWebUI prefixes API routes with /api, so this provides compatibility.
    """
    return await chat_completions(request, raw_request)
