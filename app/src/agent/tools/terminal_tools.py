"""Terminal tools using OpenHands SDK ToolDefinition pattern.

This module provides tools for executing commands in a persistent terminal environment.
All tools are registered with the OpenHands SDK tool registry.

Uses LocalWorkspace from the OpenHands SDK for synchronous command execution,
scoped per conversation via get_local_sandbox().
"""
from __future__ import annotations

import logging
import shlex
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Self

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

from app_sandbox import get_local_sandbox
from agent.prompts.loader import load_prompt

if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState

logger = logging.getLogger(__name__)


# Constants
MAX_OUTPUT_LENGTH = 8000
DEFAULT_TIMEOUT = 120.0


def truncate_output(output: str, max_length: int = MAX_OUTPUT_LENGTH) -> str:
    """Truncate output to max_length, showing beginning and end."""
    if len(output) <= max_length:
        return output

    half = max_length // 2
    truncated_count = len(output) - max_length
    return (
        output[:half] +
        f"\n\n... [{truncated_count} chars truncated] ...\n\n" +
        output[-half:]
    )


# =============================================================================
# Terminal Execute Tool
# =============================================================================

TERMINAL_EXECUTE_DESCRIPTION = """Execute a shell command in the persistent terminal environment.

The terminal preserves state across calls (installed packages, environment variables, running processes). Working directory defaults to the conversation-specific directory.

Use this for:
- Running code and scripts
- Installing packages (pip, apt-get, npm)
- Git operations
- File manipulation
- Build commands and test suites
- Data processing

After completing work that creates or modifies files, remember to list them with terminal_list_files."""


class TerminalExecuteAction(Action):
    """Action for executing a terminal command."""

    command: str = Field(
        description="The shell command to execute. Can be a single command or a multi-line script. Supports pipes, redirects, and chaining (&&, ||, ;)."
    )
    workdir: str = Field(
        default="",
        description="Working directory for the command. Leave empty for the conversation directory.",
    )
    timeout: float = Field(
        default=DEFAULT_TIMEOUT,
        description="Maximum execution time in seconds. Defaults to 120.",
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action."""
        content = Text()
        content.append("Execute command:\n", style="bold blue")
        content.append(f"$ {self.command}\n", style="green")
        content.append(f"Working dir: {self.workdir or '(conversation directory)'}", style="dim")
        return content


class TerminalExecuteObservation(TextObservation):
    """Observation from terminal command execution."""

    output: str = Field(default="", description="The command output (stdout/stderr)")
    exit_code: int = Field(default=0, description="The command exit code")

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation."""
        content = Text()
        content.append("Command output:\n", style="bold blue")
        content.append(self.output)
        return content


class TerminalExecuteExecutor(ToolExecutor):
    """Executor for terminal commands."""

    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    def __call__(
        self,
        action: TerminalExecuteAction,
        conversation: Any = None,
    ) -> TerminalExecuteObservation:
        """Execute the terminal command."""
        conv_state = conversation.state if conversation else None
        workspace = conv_state.workspace if conv_state and conv_state.workspace else get_local_sandbox().get_workspace(self.chat_id)
        resolved_workdir = action.workdir or get_local_sandbox().get_working_dir(self.chat_id)
        result = workspace.execute_command(action.command, cwd=resolved_workdir, timeout=action.timeout)
        output = f"[exit {result.exit_code}]\n{result.stdout}"
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        return TerminalExecuteObservation(output=output[:8000], exit_code=result.exit_code)


class TerminalExecuteTool(ToolDefinition[TerminalExecuteAction, TerminalExecuteObservation]):
    """Tool for executing shell commands in a persistent terminal."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,
        chat_id: str = "",
        **params,
    ) -> Sequence[Self]:
        """Create TerminalExecuteTool instance."""
        if params:
            raise ValueError(f"TerminalExecuteTool doesn't accept parameters: {params}")
        return [
            cls(
                action_type=TerminalExecuteAction,
                observation_type=TerminalExecuteObservation,
                description=TERMINAL_EXECUTE_DESCRIPTION,
                executor=TerminalExecuteExecutor(chat_id=chat_id),
                annotations=ToolAnnotations(
                    title="terminal_execute",
                    readOnlyHint=False,
                    destructiveHint=True,
                    idempotentHint=False,
                    openWorldHint=True,
                ),
            )
        ]


# =============================================================================
# Terminal Upload Tool
# =============================================================================

TERMINAL_UPLOAD_DESCRIPTION = """Upload a file to the terminal workspace.

Use this to provide data files, scripts, or configuration that the terminal needs. For text files only."""


class TerminalUploadAction(Action):
    """Action for uploading a file to the terminal."""

    path: str = Field(
        description="Destination path inside the terminal. Relative paths are resolved from the conversation directory."
    )
    content: str = Field(
        description="File content as a string."
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action."""
        content = Text()
        content.append("Upload file:\n", style="bold blue")
        content.append(f"Path: {self.path}\n", style="green")
        content.append(f"Size: {len(self.content)} chars", style="dim")
        return content


class TerminalUploadObservation(TextObservation):
    """Observation from file upload."""

    message: str = Field(default="", description="Upload result message")

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation."""
        content = Text()
        content.append("Upload result: ", style="bold blue")
        content.append(self.message)
        return content


class TerminalUploadExecutor(ToolExecutor):
    """Executor for uploading files to terminal."""

    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    def __call__(
        self,
        action: TerminalUploadAction,
        conversation: Any = None,
    ) -> TerminalUploadObservation:
        """Execute the file upload."""
        base = get_local_sandbox().get_working_dir(self.chat_id)
        p = Path(action.path) if Path(action.path).is_absolute() else Path(base) / action.path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(action.content, encoding="utf-8")
        return TerminalUploadObservation(message=f"Written: {p}")


class TerminalUploadTool(ToolDefinition[TerminalUploadAction, TerminalUploadObservation]):
    """Tool for uploading files to the terminal workspace."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,
        chat_id: str = "",
        **params,
    ) -> Sequence[Self]:
        """Create TerminalUploadTool instance."""
        if params:
            raise ValueError(f"TerminalUploadTool doesn't accept parameters: {params}")
        return [
            cls(
                action_type=TerminalUploadAction,
                observation_type=TerminalUploadObservation,
                description=TERMINAL_UPLOAD_DESCRIPTION,
                executor=TerminalUploadExecutor(chat_id=chat_id),
                annotations=ToolAnnotations(
                    title="terminal_upload",
                    readOnlyHint=False,
                    destructiveHint=False,
                    idempotentHint=False,
                    openWorldHint=False,
                ),
            )
        ]


# =============================================================================
# Terminal List Files Tool
# =============================================================================

TERMINAL_LIST_DESCRIPTION = """List files and directories in the terminal workspace.

Returns names, sizes, and modification times. Use this to explore the workspace and find files created by commands."""


class TerminalListAction(Action):
    """Action for listing files in the terminal."""

    path: str = Field(
        default="",
        description="Directory to list. Leave empty for the conversation directory.",
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action."""
        content = Text()
        content.append("List files:\n", style="bold blue")
        content.append(f"Path: {self.path or '(conversation directory)'}", style="green")
        return content


class TerminalListObservation(TextObservation):
    """Observation from listing files."""

    output: str = Field(default="", description="Directory listing output")

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation."""
        content = Text()
        content.append("Files:\n", style="bold blue")
        content.append(self.output)
        return content


class TerminalListExecutor(ToolExecutor):
    """Executor for listing files in terminal."""

    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    def __call__(
        self,
        action: TerminalListAction,
        conversation: Any = None,
    ) -> TerminalListObservation:
        """Execute the file listing."""
        conv_state = conversation.state if conversation else None
        workspace = conv_state.workspace if conv_state and conv_state.workspace else get_local_sandbox().get_workspace(self.chat_id)
        path = action.path or get_local_sandbox().get_working_dir(self.chat_id)
        result = workspace.execute_command(f"ls -la {shlex.quote(str(path))}")
        return TerminalListObservation(output=result.stdout[:8000])


class TerminalListTool(ToolDefinition[TerminalListAction, TerminalListObservation]):
    """Tool for listing files in the terminal workspace."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,
        chat_id: str = "",
        **params,
    ) -> Sequence[Self]:
        """Create TerminalListTool instance."""
        if params:
            raise ValueError(f"TerminalListTool doesn't accept parameters: {params}")
        return [
            cls(
                action_type=TerminalListAction,
                observation_type=TerminalListObservation,
                description=TERMINAL_LIST_DESCRIPTION,
                executor=TerminalListExecutor(chat_id=chat_id),
                annotations=ToolAnnotations(
                    title="terminal_list_files",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]


# =============================================================================
# Terminal Download Tool
# =============================================================================

TERMINAL_DOWNLOAD_DESCRIPTION = """Download a file from the terminal workspace.

Use this to retrieve file contents. For text files only. For large files, consider using terminal_execute with head/tail."""


class TerminalDownloadAction(Action):
    """Action for downloading a file from the terminal."""

    path: str = Field(
        description="Path to the file inside the terminal. Relative paths are resolved from the conversation directory."
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this action."""
        content = Text()
        content.append("Download file:\n", style="bold blue")
        content.append(f"Path: {self.path}", style="green")
        return content


class TerminalDownloadObservation(TextObservation):
    """Observation from file download."""

    file_content: str = Field(default="", description="File content")

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation."""
        text = Text()
        text.append("File content:\n", style="bold blue")
        text.append(self.file_content[:500])
        if len(self.file_content) > 500:
            text.append(f"\n... ({len(self.file_content) - 500} more chars)", style="dim")
        return text


class TerminalDownloadExecutor(ToolExecutor):
    """Executor for downloading files from terminal."""

    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    def __call__(
        self,
        action: TerminalDownloadAction,
        conversation: Any = None,
    ) -> TerminalDownloadObservation:
        """Execute the file download."""
        base = get_local_sandbox().get_working_dir(self.chat_id)
        p = Path(action.path) if Path(action.path).is_absolute() else Path(base) / action.path
        content = p.read_text(encoding="utf-8", errors="replace")
        return TerminalDownloadObservation(file_content=content[:200000])


class TerminalDownloadTool(ToolDefinition[TerminalDownloadAction, TerminalDownloadObservation]):
    """Tool for downloading files from the terminal workspace."""

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,
        chat_id: str = "",
        **params,
    ) -> Sequence[Self]:
        """Create TerminalDownloadTool instance."""
        if params:
            raise ValueError(f"TerminalDownloadTool doesn't accept parameters: {params}")
        return [
            cls(
                action_type=TerminalDownloadAction,
                observation_type=TerminalDownloadObservation,
                description=TERMINAL_DOWNLOAD_DESCRIPTION,
                executor=TerminalDownloadExecutor(chat_id=chat_id),
                annotations=ToolAnnotations(
                    title="terminal_download",
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

# Register all terminal tools with the OpenHands SDK
register_tool("terminal_execute", TerminalExecuteTool)
register_tool("terminal_upload", TerminalUploadTool)
register_tool("terminal_list_files", TerminalListTool)
register_tool("terminal_download", TerminalDownloadTool)


# =============================================================================
# Helper Functions for Session Integration
# =============================================================================

def get_terminal_tools(chat_id: str):
    """Get terminal tool specifications for Agent initialization.

    This returns Tool specs that reference the registered tools.
    The actual tool instances are created by the ToolDefinition.create() method.

    Args:
        chat_id: Chat/session ID for conversation directory scoping

    Returns:
        List of Tool specs for Agent initialization
    """
    from openhands.sdk import Tool

    return [
        Tool(name="terminal_execute", params={"chat_id": chat_id}),
        Tool(name="terminal_upload", params={"chat_id": chat_id}),
        Tool(name="terminal_list_files", params={"chat_id": chat_id}),
        Tool(name="terminal_download", params={"chat_id": chat_id}),
    ]


def get_terminal_system_prompt() -> str:
    """Get the terminal environment system prompt section.

    Returns:
        System prompt section describing terminal capabilities
    """
    return load_prompt("terminal_system.md")
