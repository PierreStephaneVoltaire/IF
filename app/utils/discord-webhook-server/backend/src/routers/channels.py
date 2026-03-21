"""Channel registration and management endpoints.

Provides endpoints to:
- Register a Discord channel for listening
- Unregister a channel
- List registered channels
- Manually trigger a response (for testing)
"""
from __future__ import annotations
import asyncio
import logging
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from config import (
    DEFAULT_HISTORY_LIMIT,
    AGENT_MODEL_NAME,
    AGENT_API_URL,
    MAX_HISTORY_LIMIT,
    MAX_CHUNK_CHARS,
    INTER_CHUNK_DELAY,
    AGENT_TIMEOUT,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/channels", tags=["channels"])


class ChannelRegistration(BaseModel):
    """Request to register a Discord channel."""
    channel_id: str = Field(..., description="Discord channel ID")
    history_limit: int = Field(DEFAULT_HISTORY_LIMIT, description="Number of messages to fetch for context")
    system_prompt: Optional[str] = Field(None, description="Optional system prompt override (unused — agent manages its own prompts)")


class ChannelInfo(BaseModel):
    """Information about a registered channel."""
    channel_id: str
    history_limit: int
    status: str = "registered"


class ChannelListResponse(BaseModel):
    """Response for listing channels."""
    channels: List[ChannelInfo]
    total: int


def convert_history_to_messages(
    messages: List[Any],
    bot_user_id: Optional[int] = None,
    system_prompt: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Convert Discord channel history to OpenAI chat messages format.

    Bot messages become role="assistant", human messages become role="user"
    with author attribution. This gives the agent full conversation context.

    Follows the same pattern as app/src/channels/translators/discord_translator.py
    but for full history rather than a debounced batch.
    """
    openai_messages = []

    if system_prompt:
        openai_messages.append({"role": "system", "content": system_prompt})

    for msg in messages:
        if msg.is_bot:
            # Bot's own previous replies — "assistant" role
            openai_messages.append({
                "role": "assistant",
                "content": msg.content,
            })
        else:
            # Human messages — "user" role with author attribution
            content_parts = []

            if msg.content:
                content_parts.append({
                    "type": "text",
                    "text": f"[{msg.author}]: {msg.content}",
                })

            # Handle attachments
            for att in msg.attachments:
                ct = att.get("content_type", "")
                url = att.get("url", "")
                filename = att.get("filename", "attachment")

                if ct.startswith("image/") and url:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": url},
                    })
                else:
                    content_parts.append({
                        "type": "text",
                        "text": f"[Attachment: {filename} ({ct}) — {url}]",
                    })

            if content_parts:
                openai_messages.append({
                    "role": "user",
                    "content": (
                        content_parts
                        if len(content_parts) > 1
                        else content_parts[0].get("text", "")
                    ),
                })

    return openai_messages


def chunk_response(text: str, max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    """Split response into chunks for Discord's 2000-char message limit.

    Reuses patterns from app/src/channels/chunker.py
    """
    if len(text) <= max_chars:
        return [text] if text.strip() else []

    chunks = []
    paragraphs = text.split("\n\n")

    current_chunk = ""
    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= max_chars:
            current_chunk += ("\n\n" if current_chunk else "") + para
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # Handle paragraphs longer than max_chars
            if len(para) > max_chars:
                words = para.split()
                current_chunk = ""
                for word in words:
                    if len(current_chunk) + len(word) + 1 <= max_chars:
                        current_chunk += (" " if current_chunk else "") + word
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = word
            else:
                current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


async def call_agent_api(
    messages: List[Dict[str, Any]],
    channel_id: str,
    http_client: Any,
    timeout: float = AGENT_TIMEOUT,
) -> str:
    """Send chat history to the main agent FastAPI server and return the response.

    Calls POST /v1/chat/completions on the main app (app/src/main.py).
    The agent handles all LLM routing, session management, tiering, memory, etc.

    Args:
        messages: OpenAI-format message list (role + content)
        channel_id: Discord channel ID, used as chat_id for session persistence
        http_client: httpx.AsyncClient instance
        timeout: Request timeout in seconds

    Returns:
        Agent response text
    """
    url = f"{AGENT_API_URL}/v1/chat/completions"

    # chat_id scopes the conversation session in the agent — use discord_{channel_id}
    # so each Discord channel gets its own persistent context/memory
    payload = {
        "model": AGENT_MODEL_NAME,
        "messages": messages,
        "stream": False,
        "chat_id": f"discord_{channel_id}",
    }

    try:
        response = await http_client.post(
            url,
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Agent API request failed: {e}")
        raise

    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        logger.warning("Agent API returned no choices")
        return ""

    message = choices[0].get("message", {})
    content = message.get("content", "")
    return content or ""


async def handle_discord_message(message: Any, config: Any) -> None:
    """Handle incoming Discord message by routing through the main agent API.

    Flow:
    1. Fetch full channel history (human + bot messages)
    2. Convert history to OpenAI chat format (user/assistant roles)
    3. POST to main agent's /v1/chat/completions — agent handles all logic
    4. Chunk and send agent response back to Discord

    Args:
        message: discord.Message object
        config: ChannelConfig for this channel
    """
    from discord_client import get_client

    client = get_client()

    # Fetch full history — include bot messages for context
    history = await client.fetch_history(
        config.channel_id,
        limit=config.history_limit,
    )

    logger.info(f"Fetched {len(history)} messages for channel {config.channel_id}")

    if not history:
        logger.warning("No history to send to agent")
        return

    # Convert full history to OpenAI format
    # Bot messages → role: assistant, human messages → role: user
    openai_messages = convert_history_to_messages(
        history,
        system_prompt=config.system_prompt,
    )

    if not openai_messages:
        logger.warning("No messages to send to agent")
        return

    # Get shared HTTP client from the Discord client's app state
    # The http_client is stored on the client object by main.py lifespan
    http_client = getattr(client, "http_client", None)
    if not http_client:
        logger.error("HTTP client not available on Discord client")
        return

    # Route through the main agent API
    try:
        response_text = await call_agent_api(
            messages=openai_messages,
            channel_id=str(config.channel_id),
            http_client=http_client,
        )
    except Exception as e:
        logger.error(f"Agent API call failed: {e}")
        return

    if not response_text:
        logger.info("Empty response from agent")
        return

    # Chunk response and send back to Discord
    chunks = chunk_response(response_text)
    channel = client.get_channel(config.channel_id)

    if not channel:
        logger.error(f"Could not get channel {config.channel_id}")
        return

    for chunk in chunks:
        try:
            await channel.send(chunk)
            if len(chunks) > 1:
                await asyncio.sleep(INTER_CHUNK_DELAY)
        except Exception as e:
            logger.error(f"Failed to send chunk to Discord: {e}")
            break

    logger.info(f"Sent {len(chunks)} chunks to channel {config.channel_id}")


@router.post("/register", response_model=ChannelInfo)
async def register_channel(req: ChannelRegistration, request: Request):
    """Register a Discord channel for listening.

    Once registered, every new message in the channel will:
    1. Trigger a history fetch
    2. Send that history to the main agent API
    3. Post the agent's response back to Discord
    """
    from discord_client import get_client

    try:
        channel_id = int(req.channel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid channel_id - must be numeric")

    if req.history_limit > MAX_HISTORY_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"history_limit exceeds maximum of {MAX_HISTORY_LIMIT}",
        )

    client = get_client()

    if not client.is_ready():
        raise HTTPException(status_code=503, detail="Discord client not ready")

    # Verify channel exists and is accessible
    channel = client.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found or not accessible")

    # Attach the shared HTTP client to the Discord client for use in handlers
    client.http_client = request.app.state.http_client

    # Register with message handler
    config = client.register_channel(
        channel_id=channel_id,
        history_limit=req.history_limit,
        system_prompt=req.system_prompt,
        handler=handle_discord_message,
    )

    return ChannelInfo(
        channel_id=str(channel_id),
        history_limit=config.history_limit,
        status="registered",
    )


@router.delete("/{channel_id}")
async def unregister_channel(channel_id: str):
    """Unregister a Discord channel."""
    from discord_client import get_client

    try:
        channel_id_int = int(channel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid channel_id - must be numeric")

    client = get_client()

    if client.unregister_channel(channel_id_int):
        return {"status": "unregistered", "channel_id": channel_id}
    else:
        raise HTTPException(status_code=404, detail="Channel not registered")


@router.get("/", response_model=ChannelListResponse)
async def list_channels():
    """List all registered channels."""
    from discord_client import get_client

    client = get_client()

    channels = []
    for channel_id, config in client.registered_channels.items():
        channels.append(ChannelInfo(
            channel_id=str(channel_id),
            history_limit=config.history_limit,
            status="registered",
        ))

    return ChannelListResponse(channels=channels, total=len(channels))


@router.post("/{channel_id}/trigger")
async def trigger_response(channel_id: str, request: Request):
    """Manually trigger an agent response for testing.

    Fetches history and sends it to the main agent API without
    waiting for a new Discord message.
    """
    from discord_client import get_client

    try:
        channel_id_int = int(channel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid channel_id - must be numeric")

    client = get_client()

    if channel_id_int not in client.registered_channels:
        raise HTTPException(status_code=404, detail="Channel not registered")

    config = client.registered_channels[channel_id_int]

    # Fetch full channel history including bot messages
    history = await client.fetch_history(
        channel_id_int,
        limit=config.history_limit,
    )

    if not history:
        return {"status": "no_messages", "message": "No messages found in channel history"}

    # Convert to OpenAI format
    openai_messages = convert_history_to_messages(
        history,
        system_prompt=config.system_prompt,
    )

    # Get shared HTTP client
    http_client = request.app.state.http_client

    # Route through main agent API
    try:
        response_text = await call_agent_api(
            messages=openai_messages,
            channel_id=str(channel_id_int),
            http_client=http_client,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent API call failed: {e}")

    # Send to Discord
    chunks = chunk_response(response_text)
    channel = client.get_channel(channel_id_int)

    if channel:
        for chunk in chunks:
            try:
                await channel.send(chunk)
                if len(chunks) > 1:
                    await asyncio.sleep(INTER_CHUNK_DELAY)
            except Exception as e:
                logger.error(f"Failed to send chunk: {e}")
                break

    return {
        "status": "success",
        "agent_api_url": AGENT_API_URL,
        "model": AGENT_MODEL_NAME,
        "messages_processed": len(history),
        "response_length": len(response_text),
        "chunks_sent": len(chunks) if channel else 0,
    }
