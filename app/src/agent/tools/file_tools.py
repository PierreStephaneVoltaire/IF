"""File tools using OpenHands SDK ToolDefinition pattern.

This module provides read_file, write_file, and search_files tools that
interact with the OpenTerminal filesystem via HTTP. All tools are registered
with the OpenHands SDK tool registry.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Self

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

from terminal import (
    TerminalAPIError,
    create_terminal_client,
    get_static_manager,
)

if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState

logger = logging.getLogger(__name__)


MAX_OUTPUT_LENGTH = 8000
CONVERSATION_BASE = "/home/user/conversations"


def _get_conversation_workdir(chat_id: str) -> str:
    return f"{CONVERSATION_BASE}/{chat_id}"


def _resolve_path(path: str, chat_id: str) -> str:
    if not path.startswith("/"):
        return f"{_get_conversation_workdir(chat_id)}/{path}"
    return path


def _truncate(text: str, max_len: int = MAX_OUTPUT_LENGTH) -> str:
    if len(text) <= max_len:
        return text
    return f"[Output truncated - showing first {max_len} of {len(text)} chars]\n\n{text[:max_len]}"


# =============================================================================
# read_file Tool
# =============================================================================

READ_FILE_DESCRIPTION = """Read a file from the terminal workspace.

Use this to inspect file contents. Supports optional line range for large files.
For binary files or images, use terminal_execute with appropriate commands."""


class ReadFileAction(Action):
    """Action for reading a file."""

    path: str = Field(
        description="Path to the file. Relative paths are resolved from the conversation directory."
    )
    start_line: int = Field(
        default=0,
        description="First line to return (1-indexed). 0 means start of file."
    )
    end_line: int = Field(
        default=0,
        description="Last line to return (1-indexed, inclusive). 0 means end of file."
    )

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("Read file:\n", style="bold blue")
        content.append(f"Path: {self.path}", style="green")
        if self.start_line or self.end_line:
            content.append(f" (lines {self.start_line or 1}-{self.end_line or 'end'})", style="dim")
        return content


class ReadFileObservation(Observation):
    """Observation from file read."""

    content: str = Field(default="", description="File content")

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("File content:\n", style="bold blue")
        content.append(self.content[:500])
        if len(self.content) > 500:
            content.append(f"\n... ({len(self.content) - 500} more chars)", style="dim")
        return content


class ReadFileExecutor(ToolExecutor):
    """Executor for reading files from terminal."""

    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    def __call__(
        self,
        action: ReadFileAction,
        conversation: Any = None,
    ) -> ReadFileObservation:
        import asyncio

        async def _execute():
            try:
                manager = get_static_manager()
                if manager is None:
                    return ReadFileObservation(content="ERROR: Terminal system not initialized")

                container = manager.get_or_create(self.chat_id)
                path = _resolve_path(action.path, self.chat_id)

                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    client = create_terminal_client(container, http_client)

                    kwargs: dict[str, Any] = {}
                    if action.start_line > 0:
                        kwargs["start_line"] = action.start_line
                    if action.end_line > 0:
                        kwargs["end_line"] = action.end_line

                    data = await client.read_file(path, **kwargs)
                    content = data.get("content", "")

                    if len(content) > MAX_OUTPUT_LENGTH:
                        content = _truncate(content)

                    return ReadFileObservation(content=content)

            except TerminalAPIError as e:
                return ReadFileObservation(
                    content=f"ERROR: Terminal API returned {e.status_code}: {e.message}"
                )
            except Exception as e:
                logger.error(f"[read_file] Error: {e}")
                return ReadFileObservation(content=f"ERROR: {type(e).__name__}: {e}")

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _execute())
                return future.result()
        else:
            return asyncio.run(_execute())


class ReadFileTool(ToolDefinition[ReadFileAction, ReadFileObservation]):
    """Tool for reading files from the terminal workspace."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,
        chat_id: str = "",
        **params,
    ) -> Sequence[Self]:
        if params:
            raise ValueError(f"ReadFileTool doesn't accept parameters: {params}")
        return [
            cls(
                action_type=ReadFileAction,
                observation_type=ReadFileObservation,
                description=READ_FILE_DESCRIPTION,
                executor=ReadFileExecutor(chat_id=chat_id),
                annotations=ToolAnnotations(
                    title="read_file",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]


# =============================================================================
# write_file Tool
# =============================================================================

WRITE_FILE_DESCRIPTION = """Write content to a file in the terminal workspace.

Creates parent directories automatically. Overwrites existing files.
Use for creating scripts, configuration files, code, and any text content."""


class WriteFileAction(Action):
    """Action for writing a file."""

    path: str = Field(
        description="Destination path. Relative paths are resolved from the conversation directory."
    )
    content: str = Field(
        description="File content to write."
    )

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("Write file:\n", style="bold blue")
        content.append(f"Path: {self.path}\n", style="green")
        content.append(f"Size: {len(self.content)} chars", style="dim")
        return content


class WriteFileObservation(Observation):
    """Observation from file write."""

    message: str = Field(default="", description="Write result message")

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("Write result: ", style="bold blue")
        content.append(self.message)
        return content


class WriteFileExecutor(ToolExecutor):
    """Executor for writing files to terminal."""

    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    def __call__(
        self,
        action: WriteFileAction,
        conversation: Any = None,
    ) -> WriteFileObservation:
        import asyncio

        async def _execute():
            try:
                manager = get_static_manager()
                if manager is None:
                    return WriteFileObservation(message="ERROR: Terminal system not initialized")

                container = manager.get_or_create(self.chat_id)
                path = _resolve_path(action.path, self.chat_id)

                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    client = create_terminal_client(container, http_client)

                    # Ensure parent directory exists
                    dir_path = "/".join(path.rsplit("/", 1)[:-1])
                    if dir_path:
                        try:
                            await client.execute_command(f"mkdir -p {dir_path}", timeout=5.0)
                        except Exception:
                            pass

                    await client.write_file(path, action.content)

                    return WriteFileObservation(message=f"File written successfully: {path}")

            except TerminalAPIError as e:
                return WriteFileObservation(
                    message=f"ERROR: Terminal API returned {e.status_code}: {e.message}"
                )
            except Exception as e:
                logger.error(f"[write_file] Error: {e}")
                return WriteFileObservation(message=f"ERROR: {type(e).__name__}: {e}")

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _execute())
                return future.result()
        else:
            return asyncio.run(_execute())


class WriteFileTool(ToolDefinition[WriteFileAction, WriteFileObservation]):
    """Tool for writing files to the terminal workspace."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,
        chat_id: str = "",
        **params,
    ) -> Sequence[Self]:
        if params:
            raise ValueError(f"WriteFileTool doesn't accept parameters: {params}")
        return [
            cls(
                action_type=WriteFileAction,
                observation_type=WriteFileObservation,
                description=WRITE_FILE_DESCRIPTION,
                executor=WriteFileExecutor(chat_id=chat_id),
                annotations=ToolAnnotations(
                    title="write_file",
                    readOnlyHint=False,
                    destructiveHint=True,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]


# =============================================================================
# search_files Tool
# =============================================================================

SEARCH_FILES_DESCRIPTION = """Search file contents in the terminal workspace.

Searches for text patterns across files. Supports regex, case-insensitive
matching, and glob include filters. Returns matching lines with file paths
and line numbers."""


class SearchFilesAction(Action):
    """Action for searching file contents."""

    query: str = Field(
        description="Text or regex pattern to search for."
    )
    path: str = Field(
        default="",
        description="Directory to search in. Empty uses the conversation directory."
    )
    include: list[str] = Field(
        default_factory=list,
        description="Glob patterns to filter files (e.g. ['*.py', '*.js'])."
    )
    case_insensitive: bool = Field(
        default=False,
        description="Perform case-insensitive matching."
    )
    regex: bool = Field(
        default=False,
        description="Treat query as a regex pattern."
    )
    max_results: int = Field(
        default=50,
        description="Maximum number of matches to return."
    )

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("Search files:\n", style="bold blue")
        content.append(f"Query: {self.query}", style="green")
        if self.path:
            content.append(f"\nPath: {self.path}", style="dim")
        if self.include:
            content.append(f"\nFilter: {', '.join(self.include)}", style="dim")
        return content


class SearchFilesObservation(Observation):
    """Observation from file search."""

    output: str = Field(default="", description="Search results")

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("Search results:\n", style="bold blue")
        content.append(self.output[:500])
        if len(self.output) > 500:
            content.append(f"\n... ({len(self.output) - 500} more chars)", style="dim")
        return content


class SearchFilesExecutor(ToolExecutor):
    """Executor for searching files in terminal."""

    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    def __call__(
        self,
        action: SearchFilesAction,
        conversation: Any = None,
    ) -> SearchFilesObservation:
        import asyncio

        async def _execute():
            try:
                manager = get_static_manager()
                if manager is None:
                    return SearchFilesObservation(output="ERROR: Terminal system not initialized")

                container = manager.get_or_create(self.chat_id)
                search_path = _resolve_path(action.path, self.chat_id) if action.path else _get_conversation_workdir(self.chat_id)

                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    client = create_terminal_client(container, http_client)

                    data = await client.grep_files(
                        query=action.query,
                        path=search_path,
                        include=action.include or None,
                        case_insensitive=action.case_insensitive,
                        regex=action.regex,
                        match_per_line=True,
                        max_results=action.max_results,
                    )
                    results = data.get("results", [])

                    if not results:
                        return SearchFilesObservation(output=f"No matches found for '{action.query}' in {search_path}")

                    lines = []
                    for r in results:
                        file_path = r.get("file", r.get("path", "unknown"))
                        line_num = r.get("line", r.get("line_number", "?"))
                        line_text = r.get("text", r.get("line_text", ""))
                        lines.append(f"{file_path}:{line_num}: {line_text}")

                    output = "\n".join(lines)
                    if len(output) > MAX_OUTPUT_LENGTH:
                        output = _truncate(output)

                    return SearchFilesObservation(output=output)

            except TerminalAPIError as e:
                return SearchFilesObservation(
                    output=f"ERROR: Terminal API returned {e.status_code}: {e.message}"
                )
            except Exception as e:
                logger.error(f"[search_files] Error: {e}")
                return SearchFilesObservation(output=f"ERROR: {type(e).__name__}: {e}")

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _execute())
                return future.result()
        else:
            return asyncio.run(_execute())


class SearchFilesTool(ToolDefinition[SearchFilesAction, SearchFilesObservation]):
    """Tool for searching file contents in the terminal workspace."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,
        chat_id: str = "",
        **params,
    ) -> Sequence[Self]:
        if params:
            raise ValueError(f"SearchFilesTool doesn't accept parameters: {params}")
        return [
            cls(
                action_type=SearchFilesAction,
                observation_type=SearchFilesObservation,
                description=SEARCH_FILES_DESCRIPTION,
                executor=SearchFilesExecutor(chat_id=chat_id),
                annotations=ToolAnnotations(
                    title="search_files",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]


# =============================================================================
# Tool Registration
# =============================================================================

register_tool("read_file", ReadFileTool)
register_tool("write_file", WriteFileTool)
register_tool("search_files", SearchFilesTool)
