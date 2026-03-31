"""Terminal tools using OpenHands SDK ToolDefinition pattern.

This module provides tools for executing commands in a persistent terminal environment.
All tools are registered with the OpenHands SDK tool registry.

Uses a shared terminal deployment with conversation-scoped working directories
for isolation: /home/user/conversations/{chat_id}
"""
from __future__ import annotations

import logging
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

from terminal import (
    CommandResult,
    create_terminal_client,
    get_static_manager,
)
from agent.prompts.loader import load_prompt

if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState

logger = logging.getLogger(__name__)


# Constants
MAX_OUTPUT_LENGTH = 8000
CONVERSATION_BASE = "/home/user/conversations"
DEFAULT_TIMEOUT = 120.0


def get_conversation_workdir(chat_id: str) -> str:
    """Get the conversation-specific working directory.

    Args:
        chat_id: The chat/conversation identifier

    Returns:
        Path to the conversation directory
    """
    return f"{CONVERSATION_BASE}/{chat_id}"


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


def format_command_result(result: CommandResult) -> str:
    """Format a command result for display."""
    output_parts = []

    if result.stdout:
        output_parts.append(f"STDOUT:\n{result.stdout}")

    if result.stderr:
        output_parts.append(f"STDERR:\n{result.stderr}")

    output_parts.append(f"EXIT CODE: {result.exit_code}")
    output_parts.append(f"DURATION: {result.duration_ms}ms")

    output = "\n\n".join(output_parts)
    return truncate_output(output)


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


class TerminalExecuteObservation(Observation):
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
        import asyncio

        # Run the async function in the event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        async def _execute():
            try:
                manager = get_static_manager()
                if manager is None:
                    return TerminalExecuteObservation(
                        output="ERROR: Terminal system not initialized",
                        exit_code=-1
                    )

                container = await manager.get_or_create(self.chat_id)

                # Determine workdir: explicit or conversation-scoped
                workdir = action.workdir or get_conversation_workdir(self.chat_id)

                async with httpx.AsyncClient() as http_client:
                    client = create_terminal_client(container, http_client)

                    # Ensure conversation directory exists
                    try:
                        await client.execute_command(f"mkdir -p {workdir}", timeout=5.0)
                    except Exception as e:
                        logger.debug(f"[terminal_execute] mkdir warning: {e}")

                    result = await client.execute_command(
                        action.command,
                        workdir=workdir,
                        timeout=action.timeout,
                    )

                    return TerminalExecuteObservation(
                        output=format_command_result(result),
                        exit_code=result.exit_code
                    )

            except httpx.TimeoutException:
                return TerminalExecuteObservation(
                    output=f"ERROR: Command timed out after {action.timeout}s",
                    exit_code=-1
                )

            except httpx.HTTPStatusError as e:
                return TerminalExecuteObservation(
                    output=f"ERROR: Terminal API returned {e.response.status_code}: {e.response.text}",
                    exit_code=-1
                )

            except Exception as e:
                logger.error(f"[terminal_execute] Error: {e}")
                return TerminalExecuteObservation(
                    output=f"ERROR: {type(e).__name__}: {e}",
                    exit_code=-1
                )

        if loop and loop.is_running():
            # We're in an async context, create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _execute())
                return future.result()
        else:
            return asyncio.run(_execute())


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


class TerminalUploadObservation(Observation):
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
        import asyncio

        async def _execute():
            try:
                manager = get_static_manager()
                if manager is None:
                    return TerminalUploadObservation(message="ERROR: Terminal system not initialized")

                container = await manager.get_or_create(self.chat_id)

                # Resolve path relative to conversation directory
                path = action.path
                if not path.startswith("/"):
                    conv_dir = get_conversation_workdir(self.chat_id)
                    path = f"{conv_dir}/{path}"

                async with httpx.AsyncClient() as http_client:
                    client = create_terminal_client(container, http_client)

                    # Ensure directory exists
                    dir_path = "/".join(path.rsplit("/", 1)[:-1])
                    if dir_path:
                        try:
                            await client.execute_command(f"mkdir -p {dir_path}", timeout=5.0)
                        except Exception:
                            pass

                    await client.upload_text_file(path, action.content)

                    return TerminalUploadObservation(message=f"File uploaded successfully: {path}")

            except httpx.HTTPStatusError as e:
                return TerminalUploadObservation(
                    message=f"ERROR: Terminal API returned {e.response.status_code}: {e.response.text}"
                )

            except Exception as e:
                logger.error(f"[terminal_upload] Error: {e}")
                return TerminalUploadObservation(message=f"ERROR: {type(e).__name__}: {e}")

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


class TerminalListObservation(Observation):
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
        import asyncio

        async def _execute():
            try:
                manager = get_static_manager()
                if manager is None:
                    return TerminalListObservation(output="ERROR: Terminal system not initialized")

                container = await manager.get_or_create(self.chat_id)

                # Resolve path relative to conversation directory
                path = action.path or get_conversation_workdir(self.chat_id)

                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    client = create_terminal_client(container, http_client)
                    result = await client.list_files(path)

                    # Format the listing
                    if not result:
                        return TerminalListObservation(output="(empty directory)")

                    lines = []
                    for item in result:
                        lines.append(f"{item.name}\t{item.size} bytes\t{item.modified}")

                    return TerminalListObservation(output="\n".join(lines))

            except httpx.HTTPStatusError as e:
                return TerminalListObservation(
                    output=f"ERROR: Terminal API returned {e.response.status_code}: {e.response.text}"
                )

            except Exception as e:
                logger.error(f"[terminal_list_files] Error: {e}")
                return TerminalListObservation(output=f"ERROR: {type(e).__name__}: {e}")

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


class TerminalDownloadObservation(Observation):
    """Observation from file download."""

    content: str = Field(default="", description="File content")

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation of this observation."""
        text = Text()
        text.append("File content:\n", style="bold blue")
        text.append(self.content[:500])
        if len(self.content) > 500:
            text.append(f"\n... ({len(self.content) - 500} more chars)", style="dim")
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
        import asyncio

        async def _execute():
            try:
                manager = get_static_manager()
                if manager is None:
                    return TerminalDownloadObservation(content="ERROR: Terminal system not initialized")

                container = await manager.get_or_create(self.chat_id)

                # Resolve path relative to conversation directory
                path = action.path
                if not path.startswith("/"):
                    conv_dir = get_conversation_workdir(self.chat_id)
                    path = f"{conv_dir}/{path}"

                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    client = create_terminal_client(container, http_client)
                    content = await client.download_text_file(path)

                    if len(content) > MAX_OUTPUT_LENGTH:
                        content = truncate_output(content)
                        content = f"[File truncated - {len(content)} chars shown]\n\n{content}"

                    return TerminalDownloadObservation(content=content)

            except httpx.HTTPStatusError as e:
                return TerminalDownloadObservation(
                    content=f"ERROR: Terminal API returned {e.response.status_code}: {e.response.text}"
                )

            except Exception as e:
                logger.error(f"[terminal_download] Error: {e}")
                return TerminalDownloadObservation(content=f"ERROR: {type(e).__name__}: {e}")

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
