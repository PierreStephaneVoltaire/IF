"""LocalSandbox — wraps OpenHands SDK LocalWorkspace for per-conversation shell access.

Replaces StaticTerminalManager (HTTP-based OpenTerminal pod).
Commands run as subprocesses of the FastAPI process against the mounted conversations PVC.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional

from openhands.sdk import LocalWorkspace

logger = logging.getLogger(__name__)

_manager: Optional["LocalSandboxManager"] = None

WORKSPACE_BASE = os.getenv("WORKSPACE_BASE", "/app/src/data/conversations")


class LocalSandboxManager:
    """Manages per-conversation LocalWorkspace instances."""

    def __init__(self, workspace_base: str = WORKSPACE_BASE):
        self.workspace_base = Path(workspace_base)
        self._workspaces: Dict[str, LocalWorkspace] = {}

    def get_workspace(self, chat_id: str) -> LocalWorkspace:
        """Return (creating if needed) the LocalWorkspace for this conversation."""
        if chat_id not in self._workspaces:
            workdir = self.workspace_base / chat_id
            workdir.mkdir(parents=True, exist_ok=True)
            self._workspaces[chat_id] = LocalWorkspace(working_dir=str(workdir))
        return self._workspaces[chat_id]

    def get_working_dir(self, chat_id: str) -> str:
        """Return the working directory path for a conversation."""
        return str(self.workspace_base / chat_id)

    def close(self) -> None:
        """Clears in-memory workspace cache; subprocesses are auto-cleaned by OS on app exit."""
        self._workspaces.clear()


def init_local_sandbox(workspace_base: str = WORKSPACE_BASE) -> LocalSandboxManager:
    """Initialize the global LocalSandboxManager. Call once at startup."""
    global _manager
    _manager = LocalSandboxManager(workspace_base)
    Path(workspace_base).mkdir(parents=True, exist_ok=True)
    return _manager


def get_local_sandbox() -> LocalSandboxManager:
    """Return the global LocalSandboxManager. Raises if not initialized."""
    if _manager is None:
        raise RuntimeError("LocalSandboxManager not initialized — call init_local_sandbox() first")
    return _manager
