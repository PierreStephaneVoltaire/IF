
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
from routing.cache import get_cache
from routing.commands import parse_command, CommandAction
from presets.loader import get_preset_manager
from agent.session import get_or_create_session, execute_agent
from agent.tiering import (
    estimate_context_tokens,
    check_tier,
    get_preset_for_tier,
    get_tier_for_context,
)
from terminal.files import strip_files_line, log_file_refs, FilesStripBuffer, FileRef
from config import API_MODEL_NAME

if TYPE_CHECKING:
    import httpx
    from storage.models import WebhookRecord

logger = logging.getLogger(__name__)

router = APIRouter()



SSE_PREFIX = "data: "
SSE_DONE = "data: [DONE]\n\n"


def make_sse_chunk(text: str, chunk_id: str, model: str) -> str:

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
    model: str = API_MODEL_NAME
) -> AsyncGenerator[str, None]:

    buf = FilesStripBuffer()
    
    async for chunk in original_stream:
        text = extract_text_from_sse(chunk)
        
        if text:
            emit = buf.feed(text)
            if emit:
                yield make_sse_chunk(emit, chunk_id, model)
    
    remaining, file_refs = buf.finalize()
    
    if remaining:
        yield make_sse_chunk(remaining, chunk_id, model)
    
    if file_refs:
        log_file_refs(conversation_id, file_refs)
    
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
    
    yield SSE_DONE


def resolve_cache_key(
    request_data: Dict[str, Any],
    webhook: Optional["WebhookRecord"] = None
) -> str:

    if webhook:
        config = webhook.get_config()
        return config.get("channel_id", webhook.conversation_id)

    chat_id = request_data.get("chat_id")
    if chat_id:
        return chat_id

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


def build_context_id(
    request_data: Dict[str, Any],
    webhook: Optional["WebhookRecord"] = None
) -> str:
    """Build a context ID for LanceDB storage.

    Context ID format:
    - OpenWebUI chat: openwebui_{chat_id}
    - OpenWebUI channel: openwebui_{channel_id}
    - Discord channel: discord_{channel_id}

    Args:
        request_data: The request data dict
        webhook: Optional webhook record

    Returns:
        Context ID string
    """
    if webhook:
        config = webhook.get_config()
        platform = webhook.platform.lower()
        channel_id = config.get("channel_id", webhook.conversation_id)
        return f"{platform}_{channel_id}"

    chat_id = request_data.get("chat_id")
    if chat_id:
        return f"openwebui_{chat_id}"

    # Fallback: hash of first message
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
        return f"openwebui_{hashlib.sha256(content.encode()).hexdigest()[:16]}"

    return "openwebui_default"


def extract_message_window(messages: List[Dict], window_size: int = 5) -> List[str]:

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

    messages = request_data.get("messages", [])
    stream = request_data.get("stream", False)

    cache_key = resolve_cache_key(request_data, webhook)
    context_id = build_context_id(request_data, webhook)
    
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
    
    preset_manager = get_preset_manager()
    cache = get_cache()
    
    last_user_message = extract_last_user_message(messages)
    
    cmd = parse_command(last_user_message, preset_manager.slugs())
    if cmd is not None:
        if cmd.action == CommandAction.RESET_CACHE:
            cache.evict(cache_key)
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
            # Pin to specific tier (pondering mode uses tier 2/heavy)
            cached_state = cache.get_or_create(cache_key)
            # Map preset names to tiers
            tier_map = {
                "pondering": 2,  # Heavy tier for pondering
                "heavy": 2,
                "standard": 1,
                "air": 0,
            }
            tier = tier_map.get(cmd.preset, cached_state.current_tier)
            cache.pin(cache_key, tier)
            try:
                from storage.factory import get_webhook_store
                store = get_webhook_store()
                if store:
                    await cache.persist_entry(cache_key, store._backend)
            except Exception as e:
                logger.warning(f"[Cache] Failed to persist pin: {e}")
            logger.info(f"[Cache] Pinned tier {tier} for key: {cache_key}")
            return cmd.response_text, []
        
        if cmd.action == CommandAction.NOOP:
            return cmd.response_text, []
        
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
                handler = get_command_handler(store, reflection_engine, context_id)

                command_str = f"/{cmd.action.value}"
                result = handler.handle(command_str, cmd.command_args)
                return result, []
            except ImportError as e:
                logger.error(f"[Command] Required module not available: {e}")
                return f"Command not available: {e}", []
            except Exception as e:
                logger.error(f"[Command] Error handling {cmd.action.value}: {e}")
                return f"Error executing command: {e}", []
    
    interceptor_result = await intercept_request(
        messages=messages,
        http_client=http_client,
        stream=stream
    )
    
    if interceptor_result.should_bypass_routing():
        if interceptor_result.error:
            raise Exception(f"Interceptor error: {interceptor_result.error}")
        response = interceptor_result.response
        if isinstance(response, dict):
            choices = response.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                return content, []
        return str(response), []

    # Get or create cached state for tier tracking
    cached_state = cache.get_or_create(cache_key)

    # Check for pinned tier (e.g., pondering mode)
    if cached_state.pinned and cached_state.pinned_tier is not None:
        # Use pinned tier
        selected_preset = get_preset_for_tier(cached_state.pinned_tier)
        logger.info(f"[Tiering] Using pinned tier {cached_state.pinned_tier}: {selected_preset}")
    else:
        # Estimate context tokens
        # Get system prompt estimate from session
        system_prompt = "general"  # Base system prompt, will be assembled by session
        context_tokens = estimate_context_tokens(system_prompt, messages, tool_overhead=5000)

        # Check tier based on context
        try_condensation, upgrade_tier = check_tier(context_tokens, cached_state.current_tier)

        if try_condensation:
            # Context exceeds current tier limit - could trigger condensation here
            # For now, log and continue with current tier
            logger.info(f"[Tiering] Context ({context_tokens} tokens) exceeds current tier limit, condensation may be needed")

        if upgrade_tier is not None:
            # Upgrade tier
            cached_state.current_tier = upgrade_tier
            cached_state.context_tokens = context_tokens
            logger.info(f"[Tiering] Upgraded to tier {upgrade_tier}")
        else:
            cached_state.context_tokens = context_tokens

        # Get preset for current tier (always use general preset as main agent)
        selected_preset = "general"
        logger.info(f"[Tiering] Using preset: {selected_preset} (tier {cached_state.current_tier})")

    # Persist cache state
    try:
        from storage.factory import get_webhook_store
        store = get_webhook_store()
        if store:
            await cache.persist_entry(cache_key, store._backend)
    except Exception as e:
        logger.warning(f"[Cache] Failed to persist entry: {e}")

    session = get_or_create_session(
        conversation_id=cache_key,
        preset_slug=selected_preset,
        preset_manager=preset_manager,
        messages=messages,
        context_id=context_id,
    )
    
    agent_response = await execute_agent(
        session=session,
        messages=messages,
        http_client=http_client,
        stream=stream
    )
    
    cleaned_content, file_refs = strip_files_line(agent_response.content)
    agent_response.content = cleaned_content
    
    if file_refs:
        log_file_refs(cache_key, file_refs)
    
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
                context_id=context_id,
            )
        )
    except Exception as e:
        logger.debug(f"Failed to queue conversation summary: {e}")
    
    attachments = []
    
    for ref in file_refs:
        filename = ref.path.split("/")[-1] if "/" in ref.path else ref.path
        attachments.append({
            "filename": filename,
            "url": f"/files/workspace/{cache_key}/{ref.path}",
            "local_path": ref.path,
            "content_type": "application/octet-stream",
            "description": ref.description,
        })
    
    for att_path in agent_response.attachments:
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

    if request.model != API_MODEL_NAME:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model '{request.model}'. Only '{API_MODEL_NAME}' model is supported."
        )
    
    http_client = raw_request.app.state.http_client
    
    request_data = request.model_dump(exclude_none=True)
    
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
    
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    
    if stream:
        async def generate_stream():

            yield make_sse_chunk(response_text, chunk_id, API_MODEL_NAME)
            
            finish_chunk = ChatCompletionChunk(
                id=chunk_id,
                model=API_MODEL_NAME,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(),
                        finish_reason="stop",
                    )
                ],
            )
            yield f"{SSE_PREFIX}{finish_chunk.model_dump_json()}\n\n"
            
            yield SSE_DONE
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    
    return ChatCompletionResponse(
        id=chunk_id,
        model=API_MODEL_NAME,
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

    return await chat_completions(request, raw_request)
