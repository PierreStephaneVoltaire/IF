"""Media tools using OpenHands SDK ToolDefinition pattern.

Provides the read_media tool for on-demand file and image analysis.
The main agent stays on text models; vision is only invoked per specific question.
"""
from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import logging
import mimetypes
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Optional, Self

import httpx
from pydantic import Field
from rich.text import Text

from openhands.sdk.tool.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
)
from openhands.sdk import register_tool

from config import MEDIA_AIR_PRESET, MEDIA_STANDARD_PRESET, MEDIA_HEAVY_PRESET, MEDIA_UPLOAD_DIR

if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState

logger = logging.getLogger(__name__)

UPLOADS_BASE = "/home/user/conversations"

_TIER_PRESETS = {
    0: MEDIA_AIR_PRESET,
    1: MEDIA_STANDARD_PRESET,
    2: MEDIA_HEAVY_PRESET,
}


# =============================================================================
# read_media Tool
# =============================================================================

READ_MEDIA_DESCRIPTION = """Examine a file or image and answer a specific question about it.

Use this when the operator asks about an attachment they sent. Attachments appear as:
  [Attachment: filename — uploads/filename]

Each call spawns a vision-capable model. Ask precise, targeted questions to get accurate answers.
Multiple questions about the same file require separate calls."""


class ReadMediaAction(Action):
    """Action for reading and analyzing a media file."""

    file_path: str = Field(
        description="Relative path within conversation uploads dir (e.g. 'screenshot.png' or 'uploads/screenshot.png')"
    )
    question: str = Field(
        description="Specific question to answer about the file"
    )
    context: str = Field(
        default="",
        description="Optional conversation context to help the specialist interpret the file"
    )

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("Analyzing media:\n", style="bold blue")
        content.append(f"File: {self.file_path}\n", style="green")
        content.append(f"Question: {self.question}", style="dim")
        return content


class ReadMediaObservation(Observation):
    """Observation from media analysis."""

    result: str = Field(default="", description="The specialist's answer")

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("Media analysis result:\n", style="bold blue")
        content.append(self.result)
        return content


class ReadMediaExecutor(ToolExecutor):
    """Executor for read_media tool."""

    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id

    def __call__(
        self,
        action: ReadMediaAction,
        conversation: Any = None,
    ) -> ReadMediaObservation:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self._run(action))
                result = future.result()
        else:
            result = asyncio.run(self._run(action))

        return ReadMediaObservation(result=result)

    async def _run(self, action: ReadMediaAction) -> str:
        # Normalize file_path: strip leading "uploads/" to get bare filename
        file_path = action.file_path
        if file_path.startswith("uploads/"):
            file_path = file_path[len("uploads/"):]

        full_path = f"{UPLOADS_BASE}/{self.conversation_id}/{MEDIA_UPLOAD_DIR}/{file_path}"

        # Download file from terminal
        try:
            from terminal import get_static_manager, create_terminal_client
        except ImportError as e:
            return f"ERROR: Terminal import failed: {e}"

        manager = get_static_manager()
        if manager is None:
            return "ERROR: Terminal not available"

        try:
            container = await manager.get_or_create(self.conversation_id)
            async with httpx.AsyncClient() as http_client:
                client = create_terminal_client(container, http_client)
                file_bytes = await client.download_file(full_path)
        except Exception as e:
            return f"ERROR: Could not download file '{file_path}': {e}"

        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        # Build user message content parts
        if mime_type.startswith("image/"):
            b64 = base64.b64encode(file_bytes).decode("ascii")
            file_content_part = {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{b64}"},
            }
        else:
            # Non-image: decode as text
            try:
                text_content = file_bytes.decode("utf-8", errors="replace")
            except Exception:
                text_content = repr(file_bytes[:500])
            file_content_part = {
                "type": "text",
                "text": f"[File content of {file_path}]:\n{text_content}",
            }

        # Render specialist system prompt
        from agent.specialists import get_specialist, render_specialist_prompt
        specialist = get_specialist("media_reader")
        if specialist is None:
            return "ERROR: media_reader specialist not registered"

        system_prompt = render_specialist_prompt(
            specialist=specialist,
            task=action.question,
            context=action.context,
        )

        # Select media tier preset based on current conversation tier
        tier = 0
        try:
            from routing.cache import get_cache
            state = get_cache().get(self.conversation_id)
            if state is not None:
                tier = state.current_tier
        except Exception:
            pass

        media_model = _TIER_PRESETS.get(tier, MEDIA_AIR_PRESET)

        # Call vision-capable model directly (single completion, no tool loop)
        from orchestrator.executor import call_openrouter

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    file_content_part,
                    {"type": "text", "text": action.question},
                ],
            },
        ]

        try:
            async with httpx.AsyncClient(timeout=120.0) as http_client:
                response = await call_openrouter(
                    model=media_model,
                    messages=messages,
                    http_client=http_client,
                )
            return response.content or "No response from media specialist"
        except Exception as e:
            logger.error(f"[read_media] Vision call failed: {e}")
            return f"ERROR: Vision specialist call failed: {e}"


class ReadMediaTool(ToolDefinition[ReadMediaAction, ReadMediaObservation]):
    """Tool for on-demand file and image analysis."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,
        conversation_id: str = "",
        **params,
    ) -> Sequence[Self]:
        if params:
            raise ValueError(f"ReadMediaTool doesn't accept parameters: {params}")
        return [
            cls(
                action_type=ReadMediaAction,
                observation_type=ReadMediaObservation,
                description=READ_MEDIA_DESCRIPTION,
                executor=ReadMediaExecutor(conversation_id=conversation_id),
                annotations=ToolAnnotations(
                    title="read_media",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=False,
                    openWorldHint=True,
                ),
            )
        ]


# =============================================================================
# Tool Registration
# =============================================================================

register_tool("read_media", ReadMediaTool)


# =============================================================================
# Helper Functions for Session Integration
# =============================================================================

def get_media_tools(conversation_id: str):
    """Get media tool specifications for Agent initialization.

    Args:
        conversation_id: Raw conversation ID (cache_key) for upload path resolution

    Returns:
        List of Tool specs for Agent initialization
    """
    from openhands.sdk import Tool

    return [
        Tool(name="read_media", params={"conversation_id": conversation_id}),
    ]
