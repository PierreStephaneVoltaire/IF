"""FastAPI router main module using multi-agent LangGraph flow.

This module uses LangGraph's native features:
- Checkpointer for persistence and memory
- Interrupts for human-in-the-loop
- State management with add_messages reducer
- Graph visualization
- HTTP interrupt handling and resume from checkpoint
"""
from __future__ import annotations
import asyncio
import json
import uuid
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

import time

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, PlainTextResponse

from models import (
    Model, 
    ModelList, 
    Message, 
    ChatRequest,
    UserCheckpointResponse,
    ConversationContext,
)
from helpers import normalize_message_content
from graph import (
    run_conversation_flow,
    run_conversation_flow_streaming,
    resume_conversation,
    get_graph_diagram,
    list_checkpoints,
    get_checkpoint_state,
    get_persistence_manager,
)
from streaming import (
    create_stream,
    get_stream,
    remove_stream,
    ConversationStream,
    UserResponse,
    make_openai_chunk,
    StreamMessage,
    EventType,
    CheckpointType,
)
from request_tracker import (
    get_request_tracker,
    RequestStatus,
)

app = FastAPI(
    title="LangGraph Multi-Agent Router",
    description="FastAPI router using LangGraph for persistence, memory, interrupts, and checkpoints",
)

# Shared HTTP client for connection pooling
http_client: Optional[httpx.AsyncClient] = None

# Background cleanup task
_cleanup_task: Optional[asyncio.Task] = None

OPENWEBUI_TASK_MARKERS = [
    "### Task:\nSuggest 3-5 relevant follow-up",
    "### Task:\nGenerate a concise, 3-5 word title",
    "### Task:\nGenerate 1-3 broad tags",
]

def is_openwebui_task(messages: list) -> bool:
    if not messages:
        return False
    last = messages[-1].get("content", "")
    if not isinstance(last, str):
        return False
    return any(marker in last for marker in OPENWEBUI_TASK_MARKERS)

async def cleanup_old_requests():
    """Background task to clean up old requests."""
    while True:
        try:
            await asyncio.sleep(300)  # Run every 5 minutes
            tracker = get_request_tracker()
            removed = await tracker.cleanup_old_requests()
            if removed > 0:
                print(f"[Cleanup] Removed {removed} old requests")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Cleanup] Error: {e}")


@app.on_event("startup")
async def startup_event():
    """Initialize shared HTTP client on startup."""
    global http_client, _cleanup_task
    http_client = httpx.AsyncClient(
        timeout=120.0,
        limits=httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
            keepalive_expiry=60.0
        )
    )
    
    # Set HTTP client reference in other modules
    import condenser
    import categorization
    condenser.http_client = http_client
    categorization.http_client = http_client
    
    # Start cleanup task
    _cleanup_task = asyncio.create_task(cleanup_old_requests())
    
    print("[Startup] HTTP client initialized")
    print("[Startup] Request tracker initialized")
    print("[Startup] Using LangGraph for persistence, memory, interrupts, and checkpoints")
    print("[Startup] Streaming endpoints available at /api/v1/chat/completions (stream=true)")
    print("[Startup] HTTP interrupt handling enabled - clients can resume from checkpoint")


@app.on_event("shutdown")
async def shutdown_event():
    """Close shared HTTP client on shutdown."""
    global http_client, _cleanup_task
    if http_client:
        await http_client.aclose()
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass


@app.get("/api/v1/models", response_model=ModelList)
async def list_models():
    """Return available models for OpenWebUI discovery."""
    return ModelList(
        data=[
            Model(
                id="router",
                owned_by="langgraph"
            )
        ]
    )


@app.get("/api/models", response_model=ModelList)
async def list_models_alias():
    """Alias for /api/v1/models."""
    return await list_models()


@app.post("/api/v1/chat/completions")
async def chat_completions(body: ChatRequest, request: Request):
    """Handle chat completions using multi-agent LangGraph flow.
    
    This endpoint uses LangGraph's native features:
    - Checkpointer for persistence (SQLite or Memory)
    - Memory via add_messages reducer
    - Interrupts for human-in-the-loop
    - State management
    - HTTP interrupt handling with resume capability
    
    Flow:
    1. Check for existing checkpoint (resume if found)
    2. Normalize messages
    3. If stream=true, use streaming endpoint with checkpoints
    4. Otherwise, run synchronous flow
    5. LangGraph handles persistence automatically via checkpointer
    6. Check token count and condense if needed (100k threshold)
    7. Categorize the conversation
    8. Orchestrator routes to appropriate agent
    9. For coding: planner -> executor -> evaluator loop
    10. Generate summary with file attachments
    
    HTTP Interrupt Handling:
    - If connection drops during processing, state is checkpointed
    - Client can reconnect with same chat_id to resume
    - Request tracker monitors in-flight requests
    """
    messages_dicts = [normalize_message_content(msg) for msg in body.messages]
    raw = await request.json()
    print(json.dumps(raw, indent=2))
    if is_openwebui_task(messages_dicts):
        # Bypass the graph, call LLM directly
        from categorization import call_openrouter
        result = await call_openrouter("google/gemini-2.5-flash-lite", messages_dicts)
        return result  # already in the right shape for OpenWebUI
    
    # Generate chat_id if not provided - used for sandbox folder and state persistence
    chat_id = body.chat_id or str(uuid.uuid4())
    
    # Get request tracker
    tracker = get_request_tracker()
    
    # Check if there's an existing request for this chat that can be resumed
    existing_request = await tracker.get_request_for_chat(chat_id)
    if existing_request and existing_request.status == RequestStatus.WAITING_INPUT:
        # Resume from checkpoint waiting for input
        print(f"[Resume] Found waiting request {existing_request.request_id} for chat {chat_id}")
        # Return information about the waiting checkpoint
        return {
            "status": "waiting_for_input",
            "chat_id": chat_id,
            "request_id": existing_request.request_id,
            "checkpoint_id": existing_request.checkpoint_id,
            "message": "Conversation is waiting for input. Use /api/v1/chat/checkpoint or /api/v1/chat/resume to continue.",
        }
    
    # Create or get tracked request
    tracked_request = await tracker.create_request(
        chat_id=chat_id,
        request_id=body.metadata.get("request_id") if body.metadata else None,
    )
    
    # Handle streaming mode
    if body.stream:
        print("streaming")
        return await chat_completions_stream(body, tracked_request)
    
    try:
        # Mark as processing
        await tracker.mark_processing(tracked_request.request_id)
        
        # Normalize messages
        messages_dicts = [normalize_message_content(msg) for msg in body.messages]
        
        # Run the conversation flow through LangGraph with checkpointer
        result = await run_conversation_flow(
            messages_dicts,
            chat_id=chat_id,
            enable_interrupts=False,  # No interrupts in non-streaming mode
        )
        # Debug: Log the result structure
        print(f"[DEBUG] result type: {type(result)}")
        print(f"[DEBUG] result keys: {list(result.keys()) if isinstance(result, dict) else 'NOT A DICT'}")
        print(f"[DEBUG] final_response present: {'final_response' in result if isinstance(result, dict) else 'N/A'}")
        print(f"[DEBUG] personalized_response: {result.get('personalized_response', 'MISSING') if isinstance(result, dict) else 'N/A'}")
        
        # Mark as completed
        await tracker.mark_completed(tracked_request.request_id)
        
        # Return the final response with fallback to ensure content is never empty
        final = result.get("final_response", {})
        
        # Debug: Log what we got from final_response
        print(f"[DEBUG] final type: {type(final)}")
        print(f"[DEBUG] final keys: {list(final.keys()) if isinstance(final, dict) else 'NOT A DICT'}")
        
        content = (
            final.get("choices", [{}])[0].get("message", {}).get("content", "")
            if final.get("choices")
            else ""
        )
        
        # Fallback chain: personalized_response -> workflow_result.content -> error
        if not content:
            content = result.get("personalized_response", "")
            print(f"[DEBUG] Fallback to personalized_response: {content[:50] if content else 'EMPTY'}...")
        if not content:
            content = result.get("workflow_result", {}).get("content", "")
            print(f"[DEBUG] Fallback to workflow_result.content: {content[:50] if content else 'EMPTY'}...")
        if not content:
            print("[DEBUG] All fallbacks failed, using error message")
            content = "Error: No response generated."
        
        # Build response if final_response was empty
        if not final.get("choices"):
            final = {
                "id": f"chatcmpl-{chat_id[:8]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": result.get("workflow_result", {}).get("model", "router"),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "agent_name": result.get("workflow_result", {}).get("agent_name", "unknown"),
                "category": result.get("category", ""),
                "reasoning_pattern": result.get("reasoning_pattern", ""),
                "attachments": result.get("workflow_result", {}).get("attachments", []),
            }
        else:
            final["choices"][0]["message"]["content"] = content
        
        print(f"[DEBUG] Final response content: {content[:100] if content else 'EMPTY'}...")
        return final
        
    except Exception as e:
        # Mark as failed
        await tracker.mark_failed(tracked_request.request_id, str(e))
        raise


async def chat_completions_stream(body: ChatRequest, tracked_request):
    """Handle streaming chat completions, emitting OpenAI-compatible chunks.

    Each yielded line follows the OpenAI streaming format::

        data: {"id":"chatcmpl-...","object":"chat.completion.chunk","created":...,"model":"...","choices":[{"index":0,"delta":{...},"finish_reason":null}]}

    The stream ends with::

        data: [DONE]

    Real token-level streaming is used when the underlying LLM emits
    ``on_chat_model_stream`` events via LangGraph's ``astream_events``.
    When the LLM call is non-streaming the full response is emitted as a
    single content chunk followed by the stop chunk.
    """
    messages_dicts = [normalize_message_content(msg) for msg in body.messages]
    chat_id = body.chat_id or str(uuid.uuid4())
    tracker = get_request_tracker()
    stream = create_stream(chat_id)
    await tracker.mark_processing(tracked_request.request_id)

    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    model = body.model or "router"

    async def generate_chunks():
        # Opening chunk carries the assistant role
        yield make_openai_chunk("", completion_id, model, created, role="assistant")

        content_streamed = False
        try:
            async for event in run_conversation_flow_streaming(
                messages_dicts=messages_dicts,
                chat_id=chat_id,
            ):
                event_type = event.get("event")

                if event_type == "on_chat_model_stream":
                    # Real-time token from a streaming LLM call
                    chunk = event.get("data", {}).get("chunk")
                    if chunk:
                        token = chunk.content if hasattr(chunk, "content") else str(chunk)
                        if token:
                            content_streamed = True
                            yield make_openai_chunk(token, completion_id, model, created)

                elif event_type == "on_tool_start":
                    name = event.get("name", "")
                    await tracker.update_request(
                        tracked_request.request_id,
                        last_node=name,
                    )

            # If the LLM was non-streaming, pull the final content from state
            if not content_streamed:
                final_state = await get_checkpoint_state(chat_id)
                print(f"[DEBUG-stream] final_state type: {type(final_state)}")
                print(f"[DEBUG-stream] final_state keys: {list(final_state.keys()) if isinstance(final_state, dict) else 'NOT A DICT'}")
                
                if final_state:
                    # Try final_response first (set by node_main_agent)
                    final_response = final_state.get("final_response", {})
                    if isinstance(final_response, dict) and final_response.get("choices"):
                        content = final_response.get("choices", [{}])[0].get("message", {}).get("content", "")
                        print(f"[DEBUG-stream] Got content from final_response: {content[:50] if content else 'EMPTY'}...")
                    else:
                        # Fallback to personalized_response
                        content = final_state.get("personalized_response", "")
                        print(f"[DEBUG-stream] Fallback to personalized_response: {content[:50] if content else 'EMPTY'}...")
                    
                    if not content:
                        content = (
                            final_state.get("workflow_result", {}).get("content", "")
                            if isinstance(final_state.get("workflow_result"), dict)
                            else ""
                        )
                        print(f"[DEBUG-stream] Fallback to workflow_result.content: {content[:50] if content else 'EMPTY'}...")
                    if not content:
                        print("[DEBUG-stream] All fallbacks failed, using error message")
                        content = "Error: No response generated."
                    yield make_openai_chunk(content, completion_id, model, created)

            # Stop chunk + sentinel
            yield make_openai_chunk("", completion_id, model, created, finish_reason="stop")
            yield "data: [DONE]\n\n"

            await tracker.mark_completed(tracked_request.request_id)

        except asyncio.CancelledError:
            print(f"[Interrupt] Connection closed for request {tracked_request.request_id}")
            await tracker.mark_interrupted(tracked_request.request_id)
            yield make_openai_chunk("", completion_id, model, created, finish_reason="stop")
            yield "data: [DONE]\n\n"

        except Exception as e:
            await tracker.mark_failed(tracked_request.request_id, str(e))
            yield make_openai_chunk(str(e), completion_id, model, created, finish_reason="stop")
            yield "data: [DONE]\n\n"

        finally:
            remove_stream(stream.conversation_id)

    return StreamingResponse(
        generate_chunks(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/v1/chat/checkpoint/{conversation_id}")
async def respond_to_checkpoint(
    conversation_id: str,
    response: UserCheckpointResponse,
):
    """Receive user response to a checkpoint/interrupt.
    
    This endpoint is used for human-in-the-loop flows:
    - User selects an option from presented choices
    - User answers a question
    - User chooses to continue or stop the flow
    
    LangGraph's resume mechanism is used to continue execution
    after the interrupt.
    
    Args:
        conversation_id: The conversation ID
        response: The user's response to the checkpoint
        
    Returns:
        Acknowledgment of the response
    """
    stream = get_stream(conversation_id)
    if not stream:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found or expired"
        )
    
    if not stream.is_waiting_for_input:
        raise HTTPException(
            status_code=400,
            detail="Conversation is not waiting for input"
        )
    
    # Convert pydantic model to dataclass
    user_response = UserResponse(
        conversation_id=response.conversation_id,
        checkpoint_id=response.checkpoint_id,
        action=response.action,
        selected_option_id=response.selected_option_id,
        answer_text=response.answer_text,
        metadata=response.metadata,
    )
    
    # Provide response to stream (this unblocks the interrupt)
    stream.receive_response(user_response)
    
    # Update request tracker
    tracker = get_request_tracker()
    tracked_request = await tracker.get_request_for_chat(conversation_id)
    if tracked_request:
        await tracker.mark_processing(tracked_request.request_id)
    
    return {
        "status": "received",
        "conversation_id": conversation_id,
        "checkpoint_id": response.checkpoint_id,
    }


@app.get("/api/v1/chat/request/{request_id}")
async def get_request_status(request_id: str):
    """Get the status of a tracked request.
    
    This endpoint is useful for:
    - Checking if a request is still processing
    - Determining if a request was interrupted
    - Finding the checkpoint to resume from
    
    Args:
        request_id: The request ID to check
        
    Returns:
        Request status and metadata
    """
    tracker = get_request_tracker()
    tracked = await tracker.get_request(request_id)
    
    if not tracked:
        raise HTTPException(
            status_code=404,
            detail=f"Request {request_id} not found"
        )
    
    return tracked.to_dict()


@app.get("/api/v1/chat/status/{chat_id}")
async def get_chat_status(chat_id: str):
    """Get the current status of a chat/conversation.
    
    This endpoint checks:
    - If there's an active request for this chat
    - If the request can be resumed
    - Current checkpoint state
    
    Args:
        chat_id: The conversation ID
        
    Returns:
        Chat status with resume information
    """
    tracker = get_request_tracker()
    tracked = await tracker.get_request_for_chat(chat_id)
    
    # Get checkpoint state
    checkpoint_state = await get_checkpoint_state(chat_id)
    
    result = {
        "chat_id": chat_id,
        "has_active_request": tracked is not None,
        "can_resume": False,
        "request": tracked.to_dict() if tracked else None,
        "checkpoint_state": checkpoint_state,
    }
    
    if tracked:
        result["can_resume"] = tracked.status in (
            RequestStatus.INTERRUPTED,
            RequestStatus.WAITING_INPUT,
        )
    
    return result


@app.post("/api/v1/chat/resume/{conversation_id}")
async def resume_conversation_endpoint(
    conversation_id: str,
    response: Dict[str, Any],
):
    """Resume a conversation after an interrupt using LangGraph's resume.
    
    This is the primary endpoint for human-in-the-loop flows.
    It uses LangGraph's Command(resume=...) mechanism to continue
    execution from an interrupt point.
    
    This endpoint also handles resuming from HTTP interrupts:
    - If a connection dropped during processing
    - Client can call this to resume from last checkpoint
    
    Args:
        conversation_id: The conversation ID
        response: The user's response data (can be empty for HTTP interrupt resume)
        
    Returns:
        The result after resuming
    """
    tracker = get_request_tracker()
    tracked = await tracker.get_request_for_chat(conversation_id)
    
    # Check if we can resume
    if tracked and tracked.status not in (
        RequestStatus.INTERRUPTED,
        RequestStatus.WAITING_INPUT,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume request in status: {tracked.status.value}"
        )
    
    # Mark as processing
    if tracked:
        await tracker.mark_processing(tracked.request_id)
    
    # Resume the conversation using LangGraph's resume mechanism
    result = await resume_conversation(
        chat_id=conversation_id,
        user_response=response,
    )
    
    # Mark as completed
    if tracked:
        await tracker.mark_completed(tracked.request_id)
    
    return {
        "status": "resumed",
        "conversation_id": conversation_id,
        "result": result.get("final_response", {}),
    }


@app.get("/api/v1/conversations/{conversation_id}")
async def get_conversation_status(conversation_id: str):
    """Get the current status of a conversation.
    
    This retrieves the conversation state from LangGraph's checkpointer.
    
    Args:
        conversation_id: The conversation ID
        
    Returns:
        Current conversation state from checkpoint
    """
    stream = get_stream(conversation_id)
    
    # Get state from LangGraph checkpointer
    state = await get_checkpoint_state(conversation_id)
    
    if not state and not stream:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found"
        )
    
    return ConversationContext(
        conversation_id=conversation_id,
        is_waiting_for_input=stream.is_waiting_for_input if stream else False,
        current_checkpoint=stream.checkpoint_id if stream else None,
        state=state or {},
    )


@app.get("/api/v1/conversations/{conversation_id}/checkpoints")
async def get_conversation_checkpoints(conversation_id: str):
    """List all checkpoints for a conversation.
    
    This uses LangGraph's checkpointer to list saved states.
    
    Args:
        conversation_id: The conversation ID
        
    Returns:
        List of checkpoint metadata
    """
    checkpoints = list_checkpoints(conversation_id)
    
    return {
        "conversation_id": conversation_id,
        "checkpoints": checkpoints,
    }


@app.get("/api/v1/conversations/{conversation_id}/checkpoints/{checkpoint_id}")
async def get_specific_checkpoint(conversation_id: str, checkpoint_id: str):
    """Get a specific checkpoint state.
    
    This retrieves a specific state from LangGraph's checkpointer.
    
    Args:
        conversation_id: The conversation ID
        checkpoint_id: The checkpoint ID
        
    Returns:
        State at the specified checkpoint
    """
    state = await get_checkpoint_state(conversation_id, checkpoint_id)
    
    if not state:
        raise HTTPException(
            status_code=404,
            detail=f"Checkpoint {checkpoint_id} not found for conversation {conversation_id}"
        )
    
    return {
        "conversation_id": conversation_id,
        "checkpoint_id": checkpoint_id,
        "state": state,
    }


@app.delete("/api/v1/conversations/{conversation_id}")
async def cancel_conversation(conversation_id: str):
    """Cancel an active conversation.
    
    Args:
        conversation_id: The conversation ID
        
    Returns:
        Confirmation of cancellation
    """
    stream = get_stream(conversation_id)
    if stream:
        stream.close()
        remove_stream(conversation_id)
    
    return {
        "status": "cancelled",
        "conversation_id": conversation_id,
    }


@app.get("/api/v1/graph/diagram")
async def get_graph_diagram_endpoint():
    """Get a visual diagram of the LangGraph conversation flow.
    
    This returns a Mermaid diagram showing the graph structure,
    including nodes, edges, and interrupt points.
    
    Returns:
        Mermaid diagram text
    """
    diagram = get_graph_diagram()
    
    if not diagram:
        raise HTTPException(
            status_code=500,
            detail="Could not generate graph diagram"
        )
    
    return PlainTextResponse(
        content=diagram,
        media_type="text/plain",
    )


@app.get("/api/v1/graph/mermaid")
async def get_graph_mermaid():
    """Get the Mermaid diagram for the conversation graph.
    
    Returns:
        Mermaid diagram as JSON
    """
    diagram = get_graph_diagram()
    
    return {
        "format": "mermaid",
        "diagram": diagram,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "features": {
            "persistence": "langgraph_checkpointer",
            "memory": "langgraph_add_messages",
            "interrupts": "langgraph_interrupt",
            "streaming": "langgraph_astream_events",
            "visualization": "langgraph_mermaid",
        }
    }
