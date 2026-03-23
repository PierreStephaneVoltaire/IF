"""Terminal module for connecting to a shared OpenTerminal deployment.

This module provides a client that connects to a pre-deployed terminal
instance (managed via Terraform) rather than creating containers dynamically.

The terminal uses conversation-scoped working directories for isolation:
/home/user/conversations/{chat_id}

Key components:
- TerminalConfig: Configuration dataclass for terminal settings
- StaticTerminalManager: Connects to existing terminal deployment
- StaticTerminalContainer: Data model for terminal connection
- TerminalClient: HTTP client for terminal API operations
- CommandResult: Result of command execution

Example:
    from terminal import init_static_manager, get_static_manager, create_terminal_client

    # Initialize at startup
    init_static_manager("http://open-terminal:7681", "your-api-key")

    # Get container for tool execution
    manager = get_static_manager()
    container = await manager.get_or_create("chat-123")

    # Create client and execute commands
    client = create_terminal_client(container, httpx.AsyncClient())
    result = await client.execute_command("ls -la")
    print(result.stdout)
"""
from .config import TerminalConfig
from .static_client import (
    StaticTerminalContainer,
    StaticTerminalManager,
    init_static_manager,
    get_static_manager,
)
from .client import (
    CommandResult,
    FileEntry,
    TerminalClient,
    TerminalClientError,
    TerminalTimeoutError,
    TerminalAPIError,
    create_terminal_client,
)
from .files import (
    FileRef,
    FilesStripBuffer,
    strip_files_line,
    log_file_refs,
)

__all__ = [
    # Configuration
    "TerminalConfig",
    # Static terminal management
    "StaticTerminalContainer",
    "StaticTerminalManager",
    "init_static_manager",
    "get_static_manager",
    # HTTP client
    "TerminalClient",
    "create_terminal_client",
    # Data models
    "CommandResult",
    "FileEntry",
    "FileRef",
    # FILES: line handling
    "FilesStripBuffer",
    "strip_files_line",
    "log_file_refs",
    # Exceptions
    "TerminalClientError",
    "TerminalTimeoutError",
    "TerminalAPIError",
]
