"""Sandbox directory management for conversation-scoped file isolation.

DEPRECATED (Part6 - Persistent Terminal System):
This module is deprecated and will be removed in a future version.

The sandbox MCP server has been replaced by the persistent terminal system
which provides full Docker container-based file system access via:
- Terminal tools (terminal_execute) for running commands and writing files
- Docker named volumes for persistent workspace storage
- FILES: metadata extraction for attachment handling

See:
- src/terminal/ - Container lifecycle and client
- src/terminal/files.py - FILES: line stripping and FileRef extraction
- src/api/files.py - /files/workspace/{chat_id}/ endpoint for serving files

This module is kept for backward compatibility only.
"""
# ============================================================================
# DEPRECATED: Use terminal tools instead
# ============================================================================
from __future__ import annotations
import os
from typing import Optional

from config import SANDBOX_PATH


def sandbox_path_for(conversation_id: str) -> str:
    """Get the sandbox directory for a conversation.

    Returns the sandbox directory scoped to the given conversation_id.
    Creates it if it doesn't exist. Thread-safe (os.makedirs is atomic).

    Args:
        conversation_id: Unique conversation identifier

    Returns:
        Absolute path to the conversation's sandbox directory
    """
    path = os.path.join(SANDBOX_PATH, conversation_id)
    os.makedirs(path, exist_ok=True)
    return os.path.abspath(path)


def get_sandbox_root() -> str:
    """Get the root sandbox directory.

    Returns:
        Absolute path to the root sandbox directory
    """
    os.makedirs(SANDBOX_PATH, exist_ok=True)
    return os.path.abspath(SANDBOX_PATH)


def file_in_sandbox(conversation_id: str, filepath: str) -> str:
    """Get the full path for a file in a conversation's sandbox.

    Args:
        conversation_id: Unique conversation identifier
        filepath: Relative path to the file within the conversation's sandbox

    Returns:
        Absolute path to the file
    """
    sandbox = sandbox_path_for(conversation_id)
    return os.path.join(sandbox, filepath)


def is_path_in_sandbox(conversation_id: str, filepath: str) -> bool:
    """Check if a path is within a conversation's sandbox.

    This is a security check to prevent path traversal attacks.

    Args:
        conversation_id: Unique conversation identifier
        filepath: Path to check

    Returns:
        True if the path is within the sandbox, False otherwise
    """
    real_path = os.path.realpath(filepath)
    allowed_root = os.path.realpath(sandbox_path_for(conversation_id))
    return real_path.startswith(allowed_root)
