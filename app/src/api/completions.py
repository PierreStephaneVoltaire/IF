"""Chat completions endpoint for OpenAI compatibility.

POST /v1/chat/completions - Handle chat completions with intelligent routing.
"""
from __future__ import annotations
import uuid
from typing import TYPE_CHECKING

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
from routing.cache import get_cache, is_social_pattern
from presets.loader import get_preset_manager
from agent.session import get_or_create_session, execute_agent

if TYPE_CHECKING:
    import httpx

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
    
    # Simple hash for conversation ID
    import hashlib
    content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
    
    return f"conv-{content_hash}"


@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    raw_request: Request
):
    """Handle chat completions with intelligent routing.
    
    This endpoint implements the routing pipeline:
    1. Request Interception (Step 1) - Detect OpenWebUI tasks
    2. Parallel Scoring (Step 2) - Score against presets
    3. Decision Logic (Step 3) - Select best preset
    4. Conversation State Cache (Step 4) - Cache routing decisions
    5. Agent Execution (Step 5) - Run with selected preset
    
    Args:
        request: Chat completion request
        raw_request: Raw FastAPI request object
        
    Returns:
        Chat completion response
        
    Raises:
        HTTPException: If request validation fails or processing errors occur
    """
    # Get shared HTTP client from app state
    http_client = raw_request.app.state.http_client
    
    # Convert messages to dict format for processing
    messages_dicts = [msg.model_dump(exclude_none=True) for msg in request.messages]
    
    # Step 1: Request Interception
    # Check if this is an OpenWebUI suggestion/title generation request
    interceptor_result = await intercept_request(
        messages=messages_dicts,
        http_client=http_client,
        stream=request.stream or False
    )
    
    # If interceptor handled the request, return the response directly
    if interceptor_result.should_bypass_routing():
        if interceptor_result.error:
            raise HTTPException(
                status_code=500,
                detail=interceptor_result.error
            )
        return interceptor_result.response
    
    # If interceptor detected an error but couldn't handle it
    if interceptor_result.is_suggestion_request and interceptor_result.error:
        raise HTTPException(
            status_code=500,
            detail=interceptor_result.error
        )
    
    # Validate model parameter
    if request.model != "if-prototype":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model '{request.model}'. Only 'if-prototype' model is supported."
        )
    
    # Get preset manager and conversation cache
    preset_manager = get_preset_manager()
    cache = get_cache()
    
    # Extract conversation ID
    conversation_id = extract_conversation_id(messages_dicts)
    
    # Get the last user message for cache checking
    last_user_message = ""
    for msg in reversed(messages_dicts):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            break
    
    # Step 4: Check conversation cache
    cached_state = cache.get(conversation_id)
    
    if cached_state:
        # Increment message counter
        cache.increment_message_count(conversation_id)
        
        # Check if we should reclassify
        should_reclassify = cached_state.should_reclassify(last_user_message)
        
        if not should_reclassify:
            # Reuse cached route
            print(f"[Cache] Reusing cached preset: {cached_state.active_preset}")
            
            # Create/get agent session with cached preset
            session = get_or_create_session(
                conversation_id=conversation_id,
                preset_slug=cached_state.active_preset,
                preset_manager=preset_manager
            )
            
            # Execute agent
            agent_response = await execute_agent(
                session=session,
                messages=messages_dicts,
                http_client=http_client,
                stream=request.stream or False
            )
            
            # Return response
            return ChatCompletionResponse(
                id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
                model="if-prototype",
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=ChatCompletionMessage(
                            role="assistant",
                            content=agent_response.content
                        ),
                        finish_reason=agent_response.finish_reason
                    )
                ]
            )
    
    # Step 2: Parallel Scoring (first message or reclassification needed)
    # Score conversation against all presets
    scores = await score_conversation(
        messages=messages_dicts,
        preset_manager=preset_manager,
        http_client=http_client
    )
    
    # Step 3: Decision Logic
    # Select best preset based on scores
    decision = select_preset(
        scores=scores,
        preset_manager=preset_manager
    )
    
    # Log the routing decision
    print(decision.log_message)
    
    # Step 4: Update conversation cache
    if cached_state:
        # Update existing state
        cached_state.update(decision, scores)
        print(f"[Cache] Updated preset: {decision.selected_preset}")
    else:
        # Create new state
        from routing.cache import ConversationState
        new_state = ConversationState(
            conversation_id=conversation_id,
            active_preset=decision.selected_preset,
            last_scores=scores,
            last_decision=decision
        )
        cache.set(conversation_id, new_state)
        print(f"[Cache] Created new state with preset: {decision.selected_preset}")
    
    # Step 5: Agent Execution
    # Create/get agent session with selected preset
    session = get_or_create_session(
        conversation_id=conversation_id,
        preset_slug=decision.selected_preset,
        preset_manager=preset_manager
    )
    
    # Execute agent
    agent_response = await execute_agent(
        session=session,
        messages=messages_dicts,
        http_client=http_client,
        stream=request.stream or False
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
                    content=agent_response.content
                ),
                finish_reason=agent_response.finish_reason
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
