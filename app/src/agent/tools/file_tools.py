"""File tools using OpenHands SDK ToolDefinition pattern.

This module provides read_file, write_file, and search_files tools that
interact with the local filesystem via LocalWorkspace. All tools are registered
with the OpenHands SDK tool registry.
"""
from __future__ import annotations

import logging
import shlex
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

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
from agent.tools.base import TextObservation

from sandbox import get_local_sandbox

if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState

logger = logging.getLogger(__name__)


MAX_OUTPUT_LENGTH = 8000


def _resolve_path(path: str, chat_id: str) -> str:
    if not Path(path).is_absolute():
        base = get_local_sandbox().get_working_dir(chat_id)
        return str(Path(base) / path)
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


class ReadFileObservation(TextObservation):
    """Observation from file read."""

    file_content: str = Field(default="", description="File content")

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("File content:\n", style="bold blue")
        content.append(self.file_content[:500])
        if len(self.file_content) > 500:
            content.append(f"\n... ({len(self.file_content) - 500} more chars)", style="dim")
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
        path = _resolve_path(action.path, self.chat_id)
        content = Path(path).read_text(encoding="utf-8", errors="replace")
        if action.start_line or action.end_line:
            lines = content.splitlines(keepends=True)
            start = (action.start_line - 1) if action.start_line else 0
            end = action.end_line if action.end_line else len(lines)
            content = "".join(lines[start:end])
        return ReadFileObservation(file_content=content[:200000])


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


class WriteFileObservation(TextObservation):
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
        path = _resolve_path(action.path, self.chat_id)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(action.content, encoding="utf-8")
        return WriteFileObservation(message=f"Written: {path}")


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


class SearchFilesObservation(TextObservation):
    """Observation from file search."""

    output: str = Field(default="", description="Search results")

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("Search results:\n", style="bold blue")
        content.append(self.output)
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
        conv_state = conversation.state if conversation else None
        workspace = conv_state.workspace if conv_state and conv_state.workspace else get_local_sandbox().get_workspace(self.chat_id)
        search_path = action.path or get_local_sandbox().get_working_dir(self.chat_id)
        regex_flag = "" if getattr(action, "regex", False) else "-F"
        include_flags = " ".join(f"--include={shlex.quote(p)}" for p in action.include) if action.include else ""
        cmd = f"grep -rn {regex_flag} {include_flags} {shlex.quote(action.query)} {shlex.quote(str(search_path))}".strip()
        result = workspace.execute_command(cmd)
        output = result.stdout or result.stderr
        return SearchFilesObservation(output=output[:8000])


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
