"""Terminal module for persistent Docker container management.

This module provides per-chat terminal containers backed by
Open Terminal (https://github.com/open-webui/open-terminal).

Containers use named Docker volumes (not bind mounts) so the filesystem
at /home/user survives container removal and recreation.

Key components:
- TerminalConfig: Configuration dataclass for terminal settings
- TerminalLifecycleManager: Manages container creation, health, and cleanup
- TerminalContainer: Data model for container metadata
- TerminalClient: HTTP client for terminal API operations
- CommandResult: Result of command execution

Example:
    from src.terminal import TerminalConfig, TerminalLifecycleManager, create_terminal_client
    
    config = TerminalConfig.from_env()
    manager = TerminalLifecycleManager(docker.from_env(), config)
    
    # Get or create container for a chat
    container = await manager.get_or_create("chat-123")
    
    # Create client and execute commands
    client = create_terminal_client(container, httpx.AsyncClient())
    result = await client.execute_command("ls -la")
    print(result.stdout)
    
    # Clean up when done (volume persists)
    await manager.stop("chat-123")
"""
from .config import TerminalConfig
from .lifecycle import (
    TerminalContainer,
    TerminalLifecycleManager,
    TerminalCapacityError,
    TerminalError,
    TerminalNotFoundError,
    TerminalStartupError,
    get_lifecycle_manager,
    init_lifecycle_manager,
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

# K8s client
from .k8s_client import K8sTerminalClient, K8sConfig

# K8s lifecycle manager
from .k8s_lifecycle import (
    K8sTerminalContainer,
    K8sTerminalLifecycleManager,
    K8sTerminalError,
    K8sTerminalStartupError,
    K8sTerminalNotFoundError,
    K8sTerminalCapacityError,
    get_k8s_lifecycle_manager,
    init_k8s_lifecycle_manager,
)

__all__ = [
    # Configuration
    "TerminalConfig",
    # Core classes
    "TerminalContainer",
    "TerminalLifecycleManager",
    "TerminalClient",
    # Data models
    "CommandResult",
    "FileEntry",
    "FileRef",
    # FILES: line handling
    "FilesStripBuffer",
    "strip_files_line",
    "log_file_refs",
    # Exceptions
    "TerminalError",
    "TerminalStartupError",
    "TerminalNotFoundError",
    "TerminalCapacityError",
    "TerminalClientError",
    "TerminalTimeoutError",
    "TerminalAPIError",
    # Module-level helpers
    "get_lifecycle_manager",
    "init_lifecycle_manager",
    "create_terminal_client",
    # K8s
    "K8sTerminalClient",
    "K8sConfig",
    "K8sTerminalContainer",
    "K8sTerminalLifecycleManager",
    "K8sTerminalError",
    "K8sTerminalStartupError",
    "K8sTerminalNotFoundError",
    "K8sTerminalCapacityError",
    "get_k8s_lifecycle_manager",
    "init_k8s_lifecycle_manager",
]
