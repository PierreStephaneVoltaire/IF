
from __future__ import annotations
import asyncio
import json
import uuid
import hashlib
import logging
from typing import TYPE_CHECKING, Dict, List, Any, Optional, Tuple, AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from .jobs import internal_auth, owner_scope
from execution.service import HostError, ExecutionFailure
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
from files import strip_files_line, log_file_refs, FilesStripBuffer
from flow import run_if_flow, run_specialist_flow
from flow.runner import materialize_file_ref
from flow.session_dirs import clear_session_dir, resolve_session_dir
from mcp_runtime import get_mcp_manager
from config import API_MODEL_NAME, HEALTH_HELPER_MODEL

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

    platform = request_data.get("platform")
    channel_id = request_data.get("channel_id")
    if platform and channel_id:
        return str(channel_id)

    chat_id = request_data.get("conversation_id") or request_data.get("chat_id")
    if chat_id:
        return chat_id

    return str(request_data.setdefault("_request_id", uuid.uuid4().hex))


def build_context_id(request_data, webhook=None):
    if webhook:
        return str(webhook.conversation_id)
    stable = request_data.get("conversation_id") or request_data.get("chat_id")
    if stable:
        return str(stable)
    if request_data.get("platform") and request_data.get("channel_id"):
        return str(request_data["platform"]) + "_" + str(request_data["channel_id"])
    return str(request_data.setdefault("_request_id", uuid.uuid4().hex))


def format_conversation_history(messages: List[Dict], max_messages: int = 50) -> str:









    history = messages[:-1] if len(messages) > 1 else []
    if not history:
        return ""
    history = history[-max_messages:]
    lines = []
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
            content = "\n".join(text_parts)
        if content.strip():
            lines.append(f"[{role}] {content}")
    return "\n".join(lines)

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

def _parse_json_object_args(raw_args: str) -> Dict[str, Any]:

    raw_args = raw_args.strip()
    if not raw_args:
        return {}

    parsed = json.loads(raw_args)
    if not isinstance(parsed, dict):
        raise ValueError("Tool arguments must be a JSON object.")
    return parsed

def _find_specialist_for_tool(tool_name: str) -> Optional[str]:

    try:
        from agent.specialists import list_specialists

        candidates = [
            specialist.slug
            for specialist in list_specialists()
            if tool_name in specialist.tools
        ]
        if not candidates:
            return None

        candidates.sort(key=lambda slug: (slug.endswith("_write"), slug))
        return candidates[0]
    except Exception:
        return None

def _specialist_model_override(request_data: Dict[str, Any]) -> Optional[str]:

    metadata = request_data.get("metadata")
    if not isinstance(metadata, dict):
        return None

    if metadata.get("use_health_helper_model") is True:
        return HEALTH_HELPER_MODEL
    return None

async def process_chat_completion_internal(
    request_data: Dict[str, Any],
    http_client: "httpx.AsyncClient",
    webhook: Optional["WebhookRecord"] = None,
    direct_invoke: bool = False,
) -> Tuple[str, List[Dict[str, Any]]]:

    messages = request_data.get("messages", [])
    stream = request_data.get("stream", False)

    context_id = build_context_id(request_data, webhook)
    request_data.setdefault("conversation_id", context_id)
    from flow.runner import conversation_scope
    from config import IF_USER_PK
    cache_key = conversation_scope(request_data.get("_owner", IF_USER_PK), resolve_cache_key(request_data, webhook))
    last_user_message = extract_last_user_message(messages)
    logger.info(f"[Request] cache_key={cache_key} | user={request_data.get('user', '?')} | prompt={last_user_message[:80]}")

    if direct_invoke:
        import re
        match = re.match(r'^/(\w+)\s*(.*)', last_user_message.strip(), re.DOTALL)
        if not match:
            return json.dumps({"error": "Direct tool invoke expects '/tool_name {json_args}'."}), []

        tool_name, raw_args = match.group(1), match.group(2).strip()
        try:
            args = _parse_json_object_args(raw_args)
        except (json.JSONDecodeError, ValueError) as e:
            return json.dumps({"error": f"Invalid tool arguments: {e}"}), []

        args["_conversation_id"] = cache_key
        args["_user_pk"] = request_data.get("_owner", IF_USER_PK)

        registry = get_mcp_manager()
        if not registry.has_tool(tool_name):
            return json.dumps({"error": f"Unknown tool: {tool_name}"}), []

        result = await registry.call_tool(tool_name, args)

        cleaned, file_refs = strip_files_line(result)
        if file_refs:
            log_file_refs(cache_key, file_refs)

        return cleaned, []

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

    available_tools: list[str] = []
    try:
        available_tools = get_mcp_manager().list_tool_names()
    except Exception:
        available_tools = []

    specialist_commands: dict[str, str] = {}
    try:
        from agent.specialists import get_specialist_command_map
        specialist_commands = get_specialist_command_map()
    except Exception:
        specialist_commands = {}

    cmd = parse_command(
        last_user_message,
        preset_manager.slugs(),
        available_tools=available_tools,
        specialist_commands=specialist_commands,
    )
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
            from execution.service import get_execution_service
            await get_execution_service().request("POST", "/conversations/reset", params={"owner": request_data.get("_owner", IF_USER_PK), "conversation": context_id})
            clear_session_dir(request_data, webhook, cache_key)

            return cmd.response_text, []
        
        if cmd.action == CommandAction.PIN_PRESET:
            cached_state = cache.get_or_create(cache_key)
            tier_map = {
                "pondering": 2,
                "heavy": 2,
                "standard": 1,
                "air": 0,
            }
            tier = tier_map.get(cmd.preset, cached_state.current_tier)
            cache.pin(cache_key, tier)
            if cmd.preset == "pondering":
                cached_state.pondering = True
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

        if cmd.action == CommandAction.INVOKE_TOOL:
            if not cmd.target:
                return "Error executing command: missing tool target.", []
            try:
                args = _parse_json_object_args(cmd.command_args)
            except (json.JSONDecodeError, ValueError) as e:
                return f"Error executing /{cmd.target}: {e}", []

            try:
                specialist_slug = _find_specialist_for_tool(cmd.target)
                if specialist_slug:
                    args_json = json.dumps(args, indent=2, default=str)
                    task = (
                        f"Handle the slash command /{cmd.target}. "
                        f"Call the tool '{cmd.target}' with these exact JSON arguments:\n{args_json}\n\n"
                        "Return the result to the user."
                    )
                    result = await run_specialist_flow(
                        specialist_slug=specialist_slug,
                        task=task,
                        http_client=http_client,
                        session_dir=resolve_session_dir(request_data, webhook, cache_key),
                        context_id=context_id,
                        cache_key=cache_key,
                        selected_model=_specialist_model_override(request_data),
                    owner=request_data.get("_owner", "operator"),
                    )
                    content, refs = result
                    if refs:
                        log_file_refs(cache_key, refs)
                    attachments = [att for ref in refs if (att := materialize_file_ref(ref, cache_key))]
                    return content, attachments

                registry = get_mcp_manager()
                result = await registry.call_tool(cmd.target, {**args, "_conversation_id": cache_key, "_user_pk": request_data.get("_owner", IF_USER_PK)})
                return result, []
            except Exception as e:
                logger.error(f"[Command] Error executing tool {cmd.target}: {e}")
                return f"Error executing /{cmd.target}: {type(e).__name__}: {e}", []

        if cmd.action == CommandAction.INVOKE_SPECIALIST:
            if not cmd.target:
                return "Error executing command: missing specialist target.", []
            task = cmd.command_args.strip()
            if not task:
                task = last_user_message.strip()
                slash_prefix = f"/{cmd.target}"
                if task.lower().startswith(slash_prefix.lower()):
                    task = task[len(slash_prefix):].strip()
            if not task:
                return f"/{cmd.target} requires a task or message body after the command.", []

            try:
                result = await run_specialist_flow(
                    specialist_slug=cmd.target,
                    task=task,
                    http_client=http_client,
                    session_dir=resolve_session_dir(request_data, webhook, cache_key),
                    context_id=context_id,
                    cache_key=cache_key,
                    selected_model=_specialist_model_override(request_data),
                    owner=request_data.get("_owner", "operator"),
                )
                content, refs = result
                if refs:
                    log_file_refs(cache_key, refs)
                attachments = [att for ref in refs if (att := materialize_file_ref(ref, cache_key))]
                return content, attachments
            except Exception as e:
                logger.error(f"[Command] Error executing specialist {cmd.target}: {e}")
                return f"Error executing /{cmd.target}: {type(e).__name__}: {e}", []
        
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
    
    if webhook and getattr(webhook, "pinned_specialist", ""):
        locked_specialist = webhook.pinned_specialist.strip()
        if locked_specialist:
            task = last_user_message or "No message provided."
            logger.info(f"[PinnedSpecialist] channel locked to {locked_specialist!r}")
            try:
                result = await run_specialist_flow(
                    specialist_slug=locked_specialist,
                    task=task,
                    http_client=http_client,
                    session_dir=resolve_session_dir(request_data, webhook, cache_key),
                    context_id=context_id,
                    cache_key=cache_key,
                    selected_model=_specialist_model_override(request_data),
                    owner=request_data.get("_owner", "operator"),
                )
                content, refs = result
                if refs:
                    log_file_refs(cache_key, refs)
                attachments = [att for ref in refs if (att := materialize_file_ref(ref, cache_key))]
                return content, attachments
            except Exception as e:
                logger.error(f"[PinnedSpecialist] {locked_specialist} failed: {e}")
                return (
                    f"The channel is locked to the **{locked_specialist}** specialist "
                    f"but that run failed: `{type(e).__name__}: {e}`"
                ), []

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

    cached_state = cache.get_or_create(cache_key)
    if cached_state.pondering or (cached_state.pinned and cached_state.pinned_tier == 2):
        request_data["_thinking_mode_requested"] = True

    try:
        from storage.factory import get_webhook_store
        store = get_webhook_store()
        if store:
            await cache.persist_entry(cache_key, store._backend)
    except Exception as e:
        logger.warning(f"[Cache] Failed to persist entry: {e}")

    flow_result = await run_if_flow(
        request_data=request_data,
        http_client=http_client,
        cache_key=cache_key,
        context_id=context_id,
        webhook=webhook,
    )

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

    try:
        import asyncio
        from agent.reflection import get_reflection_engine

        reflection_engine = get_reflection_engine()
        if reflection_engine:
            turn_count = sum(1 for msg in messages if msg.get("role") in {"user", "assistant"})
            recent_messages = list(reversed(extract_message_window(messages, window_size=8)))
            reflection_summary = (
                "Recent messages:\n"
                + "\n".join(f"- {item[:500]}" for item in recent_messages)
                + "\n\nIF response:\n"
                + flow_result.content[:3000]
            )
            asyncio.create_task(
                reflection_engine.run_post_session(
                    session_id=cache_key,
                    turn_count=turn_count,
                    summary=reflection_summary[:5000],
                )
            )
    except Exception as e:
        logger.debug(f"Failed to queue post-session reflection: {e}")
    
    attachments = []
    for ref in flow_result.file_refs:
        att = materialize_file_ref(ref, cache_key)
        if att:
            attachments.append(att)

    logger.info(f"[Response] cache_key={cache_key} | content_len={len(flow_result.content)} | attachments={len(attachments)}")
    return flow_result.content, attachments


async def _stream_completion(
    request_data: Dict[str, Any],
    http_client: "httpx.AsyncClient",
    chunk_id: str,
    direct_invoke: bool,
) -> AsyncGenerator[str, None]:
    events: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()

    async def emit(event: str, data: dict[str, Any]) -> None:
        await events.put((event, data))

    request_data["_emit"] = emit
    response_task = asyncio.create_task(
        process_chat_completion_internal(
            request_data=request_data,
            http_client=http_client,
            direct_invoke=direct_invoke,
        )
    )
    streamed = False
    buffer = FilesStripBuffer()
    response_text = ""
    try:
        while True:
            if response_task.done():
                while not events.empty():
                    event, data = events.get_nowait()
                    if event == "delta" and data.get("delta"):
                        streamed = True
                        emitted = buffer.feed(str(data["delta"]))
                        if emitted:
                            yield make_sse_chunk(emitted, chunk_id, API_MODEL_NAME)
                response_text, _ = response_task.result()
                break
            pending_event = asyncio.create_task(events.get())
            done, _ = await asyncio.wait({response_task, pending_event}, return_when=asyncio.FIRST_COMPLETED)
            if pending_event not in done:
                pending_event.cancel()
                await asyncio.gather(pending_event, return_exceptions=True)
                continue
            event, data = pending_event.result()
            if event != "delta" or not data.get("delta"):
                continue
            streamed = True
            emitted = buffer.feed(str(data["delta"]))
            if emitted:
                yield make_sse_chunk(emitted, chunk_id, API_MODEL_NAME)

        remaining, file_refs = buffer.finalize()
        if not streamed:
            response_text, direct_refs = strip_files_line(response_text)
            file_refs.extend(direct_refs)
        if remaining:
            yield make_sse_chunk(remaining, chunk_id, API_MODEL_NAME)
        if file_refs:
            log_file_refs(build_context_id(request_data), file_refs)
        if not streamed and response_text:
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
    except (HostError, ExecutionFailure) as exc:
        yield "data: " + json.dumps({"error": {"code": exc.code, "message": str(exc)}}) + "\n\n"
        yield SSE_DONE
    finally:
        if not response_task.done():
            response_task.cancel()
            try:
                await response_task
            except asyncio.CancelledError:
                pass

@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    raw_request: Request
):

    internal_auth(raw_request.headers.get("X-Internal-Token", ""))
    owner = owner_scope(None, raw_request.headers.get("X-Person-Pk", ""))
    if request.model not in {API_MODEL_NAME, "gpt-5.6-sol", "gpt-6-astra"}:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model '{request.model}'. Only '{API_MODEL_NAME}' model is supported."
        )
    
    http_client = raw_request.app.state.http_client
    
    request_data = request.model_dump(exclude_none=True)
    request_data["_owner"] = owner
    request_data["_idempotency_key"] = raw_request.headers.get("Idempotency-Key") or uuid.uuid4().hex
    
    stream = request_data.get("stream", False)
    
    direct_invoke = raw_request.headers.get("X-Direct-Tool-Invoke", "").lower() == "true"
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"

    if stream:
        return StreamingResponse(
            _stream_completion(request_data, http_client, chunk_id, direct_invoke),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    try:
        response_text, attachments = await process_chat_completion_internal(
            request_data=request_data,
            http_client=http_client,
            direct_invoke=direct_invoke,
        )
    except HostError as exc:
        raise HTTPException(exc.status, {"code": exc.code, "message": str(exc)}) from exc
    except ExecutionFailure as exc:
        raise HTTPException(503, {"code": exc.code, "message": str(exc)}) from exc
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
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
