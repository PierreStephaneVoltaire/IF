"""Chat completions endpoint for OpenAI compatibility.

POST /v1/chat/completions - Handle chat completions with intelligent routing.

This module provides both:
1. HTTP endpoint for OpenAI-compatible API
2. Internal pipeline function for channel integrations
"""
from __future__ import annotations
import json
import uuid
import hashlib
import logging
from typing import TYPE_CHECKING, Dict, List, Any, Optional, Tuple, AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from .schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
)
from routing.interceptor import intercept_request
from routing.scorer import score_conversation
from routing.decision import select_preset
from routing.cache import get_cache, ConversationState
from routing.commands import parse_command, CommandAction
from routing.topic_shift import should_check_shift, topic_has_shifted
from presets.loader import get_preset_manager
from agent.session import get_or_create_session, execute_agent
from src.terminal.files import strip_files_line, log_file_refs, FilesStripBuffer, FileRef

if TYPE_CHECKING:
    import httpx
    from storage.models import WebhookRecord

logger = logging.getLogger(__name__)

router = APIRouter()

# Message count before checking for topic shift on pinned presets
RECLASSIFY_MESSAGE_COUNT = 5


# ============================================================================
# Part4: Streaming FILES: Stripping Support
# ============================================================================

# SSE prefix for streaming responses
SSE_PREFIX = "data: "
SSE_DONE = "data: [DONE]\n\n"


def make_sse_chunk(text: str, chunk_id: str, model: str) -> str:
    """Create an SSE-formatted chunk for streaming.
    
    Args:
        text: Text content to include in the chunk
        chunk_id: Chat completion ID
        model: Model name
        
    Returns:
        SSE-formatted string
    """
    chunk = ChatCompletionChunk(
        id=chunk_id,
        model=model,
        choices=[
            ChatCompletionChunkChoice(
                index=0,
                delta=ChatCompletionChunkDelta(content=text),
                finish_reason=None,
            )
        ],
    )
    return f"{SSE_PREFIX}{chunk.model_dump_json()}\n\n"


def extract_text_from_sse(chunk: str) -> str:
    """Extract text content from an SSE chunk.
    
    Args:
        chunk: SSE-formatted chunk string
        
    Returns:
        Extracted text content, or empty string if not parseable
    """
    if not chunk.startswith(SSE_PREFIX):
        return ""
    
    json_str = chunk[len(SSE_PREFIX):].strip()
    if not json_str or json_str == "[DONE]":
        return ""
    
    try:
        data = json.loads(json_str)
        choices = data.get("choices", [])
        if choices:
            delta = choices[0].get("delta", {})
            return delta.get("content", "")
    except json.JSONDecodeError:
        pass
    
    return ""


async def stream_with_files_strip(
    original_stream: AsyncGenerator[str, None],
    conversation_id: str,
    chunk_id: str,
    model: str = "if-prototype"
) -> AsyncGenerator[str, None]:
    """Wrap a streaming response with FILES: line stripping.
    
    Part4: This generator buffers the tail of the stream to ensure
    the FILES: line is completely captured before stripping it.
    
    Args:
        original_stream: The original streaming generator
        conversation_id: Conversation ID for logging
        chunk_id: Chat completion chunk ID
        model: Model name for SSE chunks
        
    Yields:
        SSE-formatted chunks with FILES: line stripped
    """
    buf = FilesStripBuffer()
    
    async for chunk in original_stream:
        # Extract text delta from SSE chunk
        text = extract_text_from_sse(chunk)
        
        if text:
            # Feed to buffer
            emit = buf.feed(text)
            if emit:
                yield make_sse_chunk(emit, chunk_id, model)
    
    # Finalize and get remaining text
    remaining, file_refs = buf.finalize()
    
    if remaining:
        yield make_sse_chunk(remaining, chunk_id, model)
    
    # Log extracted file references
    if file_refs:
        log_file_refs(conversation_id, file_refs)
    
    # Send finish chunk
    finish_chunk = ChatCompletionChunk(
        id=chunk_id,
        model=model,
        choices=[
            ChatCompletionChunkChoice(
                index=0,
                delta=ChatCompletionChunkDelta(),
                finish_reason="stop",
            )
        ],
    )
    yield f"{SSE_PREFIX}{finish_chunk.model_dump_json()}\n\n"
    
    # Send [DONE] marker
    yield SSE_DONE


def resolve_cache_key(
    request_data: Dict[str, Any],
    webhook: Optional["WebhookRecord"] = None
) -> str:
    """Resolve a stable cache key for the conversation.
    
    Priority:
    1. Webhook channel_id (for Discord/OpenWebUI webhooks)
    2. Request chat_id (for API clients like OpenWebUI)
    3. Hash of first message (fallback)
    
    Args:
        request_data: Request body dict
        webhook: Optional webhook record
        
    Returns:
        Cache key string
    """
    # Webhook takes priority
    if webhook:
        config = webhook.get_config()
        return config.get("channel_id", webhook.conversation_id)
    
    # Explicit chat_id
    chat_id = request_data.get("chat_id")
    if chat_id:
        return chat_id
    
    # Fallback: hash first message
    messages = request_data.get("messages", [])
    if messages:
        content = messages[0].get("content", "")
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif isinstance(part, str):
                    text_parts.append(part)
            content = " ".join(text_parts)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    return "default"


def extract_message_window(messages: List[Dict], window_size: int = 5) -> List[str]:
    """Extract recent message texts for topic shift detection.
    
    Args:
        messages: List of message dicts
        window_size: Number of recent messages to include
        
    Returns:
        List of message content strings
    """
    window = []
    for msg in reversed(messages[-window_size:]):
        content = msg.get("content", "")
        if isinstance(content, str):
            window.append(content)
        elif isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
            if text_parts:
                window.append(" ".join(text_parts))
    return window


def extract_last_user_message(messages: List[Dict]) -> str:
    """Extract the last user message content.
    
    Args:
        messages: List of message dicts
        
    Returns:
        Last user message content as string
    """
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                return " ".join(text_parts)
    return ""


async def process_chat_completion_internal(
    request_data: Dict[str, Any],
    http_client: "httpx.AsyncClient",
    webhook: Optional["WebhookRecord"] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Core pipeline for processing chat completions.
    
    This is the internal function that handles:
    Step 0: Command Parsing (slash commands)
    Step 1: Request Interception (OpenWebUI tasks)
    Step 2: Cache Check (pinned presets, topic shift)
    Step 3: Parallel Scoring (preset selection)
    Step 4: Decision Logic (best preset)
    Step 5: Agent Execution (run with selected preset)
    
    Used by:
    - POST /v1/chat/completions (HTTP clients)
    - Channel dispatcher (Discord, OpenWebUI)
    
    Args:
        request_data: Dict matching ChatCompletionRequest shape.
                      Must include 'messages'. Can include 'chat_id'.
        http_client: Shared async HTTP client for API calls
        webhook: Optional webhook record for channel integrations
        
    Returns:
        Tuple of (response_text, attachments) where attachments is a list of dicts
        with keys: filename, content_type, url, local_path.
        
    Raises:
        Exception: If processing fails at any stage
    """
    messages = request_data.get("messages", [])
    stream = request_data.get("stream", False)
    
    # Resolve cache key (chat_id or channel_id)
    cache_key = resolve_cache_key(request_data, webhook)
    
    # Record activity for heartbeat system
    try:
        from heartbeat.activity import ActivityTracker
        from storage.factory import get_webhook_store
        store = get_webhook_store()
        if store and hasattr(store, '_backend'):
            tracker = ActivityTracker(store._backend)
            webhook_id = webhook.webhook_id if webhook else None
            tracker.record_activity(cache_key, webhook_id=webhook_id)
    except Exception as e:
        logger.debug(f"[Activity] Failed to record: {e}")
    
    # Get preset manager and conversation cache
    preset_manager = get_preset_manager()
    cache = get_cache()
    
    # Extract last user message
    last_user_message = extract_last_user_message(messages)
    
    # Step 0: Command Parsing (before any routing)
    cmd = parse_command(last_user_message, preset_manager.slugs())
    if cmd is not None:
        if cmd.action == CommandAction.RESET_CACHE:
            # Evict from in-memory cache
            cache.evict(cache_key)
            # Persist eviction to SQLite (fire-and-forget)
            try:
                from storage.factory import get_webhook_store
                store = get_webhook_store()
                if store:
                    await cache.persist_eviction(cache_key, store._backend)
            except Exception as e:
                logger.warning(f"[Cache] Failed to persist eviction: {e}")
            logger.info(f"[Cache] Evicted cache key: {cache_key}")
            return cmd.response_text, []
        
        if cmd.action == CommandAction.PIN_PRESET:
            # Create or update cache entry with pinned preset
            cached_state = cache.get(cache_key)
            if cached_state:
                cache.pin(cache_key, cmd.preset)
            else:
                # Create new pinned state
                new_state = ConversationState(
                    cache_key=cache_key,
                    active_preset=cmd.preset,
                    pinned=True,
                    pin_message_count=0,
                )
                cache.set(cache_key, new_state)
            # Persist to SQLite (fire-and-forget)
            try:
                from storage.factory import get_webhook_store
                store = get_webhook_store()
                if store:
                    await cache.persist_entry(cache_key, store._backend)
            except Exception as e:
                logger.warning(f"[Cache] Failed to persist pin: {e}")
            logger.info(f"[Cache] Pinned preset '{cmd.preset}' for key: {cache_key}")
            return cmd.response_text, []
        
        if cmd.action == CommandAction.NOOP:
            # Unknown command, return error message
            return cmd.response_text, []
        
        # Part8: Handle reflection/memory commands
        if cmd.action in (CommandAction.REFLECT, CommandAction.GAPS,
                          CommandAction.PATTERNS, CommandAction.OPINIONS,
                          CommandAction.GROWTH, CommandAction.META,
                          CommandAction.TOOLS):
            try:
                from memory.user_facts import get_user_fact_store
                from agent.commands import get_command_handler
                from agent.reflection import get_reflection_engine
                
                store = get_user_fact_store()
                reflection_engine = get_reflection_engine()
                handler = get_command_handler(store, reflection_engine)
                
                # Build command string with args
                command_str = f"/{cmd.action.value}"
                result = handler.handle(command_str, cmd.command_args)
                return result, []
            except ImportError as e:
                logger.error(f"[Command] Required module not available: {e}")
                return f"Command not available: {e}", []
            except Exception as e:
                logger.error(f"[Command] Error handling {cmd.action.value}: {e}")
                return f"Error executing command: {e}", []
    
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
    
    # Step 2: Check conversation cache
    cached_state = cache.get(cache_key)
    selected_preset = None
    
    if cached_state and cached_state.pinned:
        # Pinned preset logic
        if cached_state.active_preset == "pondering":
            # Pondering pins never auto-release
            selected_preset = cached_state.active_preset
            logger.info(f"[Cache] Pondering mode active, skipping topic shift")
        else:
            # Increment pin message count
            cached_state.pin_message_count += 1
            
            if cached_state.pin_message_count >= RECLASSIFY_MESSAGE_COUNT:
                # Check for topic shift
                current_window = extract_message_window(messages)
                
                if should_check_shift(cached_state.anchor_window, current_window):
                    shifted = await topic_has_shifted(
                        cached_state.anchor_window,
                        current_window,
                        http_client
                    )
                    
                    if shifted:
                        # Topic shifted, release pin and fall through to scoring
                        cached_state.pinned = False
                        cached_state.pin_message_count = 0
                        logger.info(f"[Cache] Topic shifted, releasing pin")
                    else:
                        selected_preset = cached_state.active_preset
                else:
                    selected_preset = cached_state.active_preset
            else:
                selected_preset = cached_state.active_preset
    
    elif cached_state:
        # Normal cache logic (warm cache)
        should_reclassify = cached_state.should_reclassify(last_user_message)
        
        if not should_reclassify:
            logger.info(f"[Cache] Reusing cached preset: {cached_state.active_preset}")
            selected_preset = cached_state.active_preset
    
    # Step 3: Parallel Scoring (if no cached preset or reclassification needed)
    if selected_preset is None:
        scores = await score_conversation(
            messages=messages,
            preset_manager=preset_manager,
            http_client=http_client
        )
        
        # Step 4: Decision Logic
        decision = select_preset(
            scores=scores,
            preset_manager=preset_manager
        )
        
        # Log the routing decision
        logger.info(decision.log_message)
        selected_preset = decision.selected_preset
        
        # Update conversation cache
        current_window = extract_message_window(messages)
        
        if cached_state:
            cached_state.update(decision, scores, current_window)
            logger.info(f"[Cache] Updated preset: {decision.selected_preset}")
        else:
            new_state = ConversationState(
                cache_key=cache_key,
                active_preset=decision.selected_preset,
                anchor_window=current_window,
                last_scores=scores,
                last_decision=decision
            )
            cache.set(cache_key, new_state)
            logger.info(f"[Cache] Created new state with preset: {decision.selected_preset}")
        
        # Persist to SQLite (fire-and-forget)
        try:
            from storage.factory import get_webhook_store
            store = get_webhook_store()
            if store:
                await cache.persist_entry(cache_key, store._backend)
        except Exception as e:
            logger.warning(f"[Cache] Failed to persist entry: {e}")
    
    # Step 5: Agent Execution
    session = get_or_create_session(
        conversation_id=cache_key,
        preset_slug=selected_preset,
        preset_manager=preset_manager,
        messages=messages  # Pass messages for operator context retrieval
    )
    
    agent_response = await execute_agent(
        session=session,
        messages=messages,
        http_client=http_client,
        stream=stream
    )
    
    # Part4: Strip FILES: line from response content
    # This runs after agent returns and before response is serialized
    cleaned_content, file_refs = strip_files_line(agent_response.content)
    agent_response.content = cleaned_content
    
    # Log extracted file references
    if file_refs:
        log_file_refs(cache_key, file_refs)
    
    # Fire-and-forget conversation summary (Phase2)
    try:
        import asyncio
        from memory.summarizer import summarize_and_store
        username = request_data.get("user", "operator")
        asyncio.create_task(
            summarize_and_store(
                cache_key=cache_key,
                messages=messages,
                username=username,
                http_client=http_client,
            )
        )
    except Exception as e:
        logger.debug(f"Failed to queue conversation summary: {e}")
    
    # Build attachments list from FILES: metadata
    # Part4: Use file_refs extracted from FILES: line instead of sandbox scanning
    attachments = []
    
    # Primary: Use file references from FILES: line
    for ref in file_refs:
        # Extract filename from path
        filename = ref.path.split("/")[-1] if "/" in ref.path else ref.path
        attachments.append({
            "filename": filename,
            "url": f"/files/workspace/{cache_key}/{ref.path}",
            "local_path": ref.path,
            "content_type": "application/octet-stream",
            "description": ref.description,
        })
    
    # Fallback: Include any attachments from agent response (legacy sandbox scanning)
    for att_path in agent_response.attachments:
        # Avoid duplicates
        if not any(a["local_path"] == att_path for a in attachments):
            attachments.append({
                "filename": att_path,
                "url": f"/files/sandbox/{cache_key}/{att_path}",
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
    Supports both streaming and non-streaming responses.
    
    Args:
        request: Chat completion request
        raw_request: Raw FastAPI request object
        
    Returns:
        Chat completion response (streaming or non-streaming)
        
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
    
    # Check if streaming is requested
    stream = request_data.get("stream", False)
    
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
    
    # Generate chunk ID for streaming
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    
    # Handle streaming response
    if stream:
        # For streaming, we need to wrap the response with FILES: stripping
        # Since process_chat_completion_internal already stripped FILES:,
        # we can stream the cleaned content directly
        async def generate_stream():
            """Generate SSE stream with FILES: stripping support."""
            # Stream the response text in chunks
            # For simplicity, we send the entire response as one chunk
            # A more sophisticated implementation would chunk by sentences/tokens
            yield make_sse_chunk(response_text, chunk_id, "if-prototype")
            
            # Send finish chunk
            finish_chunk = ChatCompletionChunk(
                id=chunk_id,
                model="if-prototype",
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(),
                        finish_reason="stop",
                    )
                ],
            )
            yield f"{SSE_PREFIX}{finish_chunk.model_dump_json()}\n\n"
            
            # Send [DONE] marker
            yield SSE_DONE
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    
    # Return non-streaming OpenAI-compatible response
    return ChatCompletionResponse(
        id=chunk_id,
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
