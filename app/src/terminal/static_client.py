"""Static terminal client for connecting to an existing terminal deployment.

This module provides a client that connects to a pre-deployed terminal
instance (managed via IaC) rather than creating containers dynamically.

Usage:
    from terminal.static_client import init_static_manager, get_static_manager

    # Initialize at startup
    init_static_manager("http://open-terminal:7681", "your-api-key")

    # Get container for tool execution
    manager = get_static_manager()
    container = await manager.get_or_create(chat_id)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class StaticTerminalContainer:
    """Metadata for a static terminal deployment.

    This class mimics the TerminalContainer interface for compatibility
    with existing terminal tools.

    Attributes:
        internal_url: URL for API calls
        api_key: API key for authentication
        status: Always "ready" for static terminal
    """
    internal_url: str
    api_key: str
    status: str = "ready"

    def touch(self) -> None:
        """No-op for static terminal (always ready)."""
        pass

    @property
    def idle_seconds(self) -> float:
        """Always 0 for static terminal."""
        return 0.0


class StaticTerminalManager:
    """Manager for a statically-deployed terminal.

    Instead of creating containers, this manager connects to an
    existing terminal deployment (created via Terraform).

    Conversation isolation is handled via working directories:
    /home/user/conversations/{chat_id}

    Example:
        manager = StaticTerminalManager("http://open-terminal:7681", "api-key")
        container = await manager.get_or_create("chat-123")
        # Use container.internal_url for API calls
    """

    def __init__(self, url: str, api_key: str):
        """Initialize the static terminal manager.

        Args:
            url: URL of the terminal API (e.g., "http://open-terminal:7681")
            api_key: API key for authentication
        """
        self._url = url
        self._api_key = api_key
        self._container: Optional[StaticTerminalContainer] = None
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client for health checks."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=5.0)
        return self._http_client

    async def close(self) -> None:
        """Clean up resources.

        Should be called during application shutdown.
        """
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def get_or_create(self, chat_id: str) -> StaticTerminalContainer:
        """Return the static terminal container.

        The chat_id is ignored since there's only one shared terminal.
        Conversation isolation is handled via working directories.

        Args:
            chat_id: Chat/conversation identifier (used for logging only)

        Returns:
            StaticTerminalContainer with status "ready"
        """
        if self._container is None:
            self._container = StaticTerminalContainer(
                internal_url=self._url,
                api_key=self._api_key,
            )
            logger.info(f"[Terminal] Connected to static terminal at {self._url}")
        return self._container

    async def health_check(self) -> bool:
        """Check if the terminal is healthy.

        Returns:
            True if terminal is healthy, False otherwise
        """
        try:
            client = await self._get_http_client()
            resp = await client.get(
                f"{self._url}/api/health",
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=5.0,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"[Terminal] Health check failed: {e}")
            return False

    async def stop(self, chat_id: str) -> None:
        """No-op for static terminal.

        The terminal is managed by Terraform, not by the application.
        """
        pass

    async def stop_all(self) -> None:
        """No-op for static terminal."""
        pass

    async def cleanup_idle(self, max_idle_seconds: Optional[int] = None) -> list[str]:
        """No-op for static terminal.

        Returns:
            Empty list (no containers cleaned up)
        """
        return []

    def get_container(self, chat_id: str) -> Optional[StaticTerminalContainer]:
        """Get the static container without creating a new one.

        Args:
            chat_id: Chat/conversation identifier (ignored)

        Returns:
            StaticTerminalContainer if initialized, None otherwise
        """
        return self._container


# Global instance
_static_manager: Optional[StaticTerminalManager] = None


def init_static_manager(url: str, api_key: str) -> StaticTerminalManager:
    """Initialize the global static terminal manager.

    Args:
        url: URL of the terminal API
        api_key: API key for authentication

    Returns:
        The initialized StaticTerminalManager
    """
    global _static_manager
    _static_manager = StaticTerminalManager(url, api_key)
    logger.info(f"[Terminal] Static terminal manager initialized: {url}")
    return _static_manager


def get_static_manager() -> Optional[StaticTerminalManager]:
    """Get the global static terminal manager instance.

    Returns:
        StaticTerminalManager if initialized, None otherwise
    """
    return _static_manager
