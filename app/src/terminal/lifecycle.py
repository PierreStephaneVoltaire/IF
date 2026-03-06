"""Container lifecycle manager for per-conversation terminal containers.

This module manages the full lifecycle of per-conversation Open Terminal
Docker containers, providing on-demand creation, health checking, and
cleanup of idle containers.

Containers use named Docker volumes (not bind mounts) so the filesystem
at /home/user survives container removal and recreation.

Reference: https://github.com/open-webui/open-terminal
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import docker
import httpx

from .config import TerminalConfig

if TYPE_CHECKING:
    from docker.models.containers import Container

logger = logging.getLogger(__name__)


# ============================================================================
# Exceptions
# ============================================================================

class TerminalError(Exception):
    """Base exception for terminal container errors."""
    pass


class TerminalStartupError(TerminalError):
    """Raised when a terminal container fails to start within timeout."""
    
    def __init__(self, chat_id: str, timeout: float, details: str = ""):
        self.chat_id = chat_id
        self.timeout = timeout
        self.details = details
        msg = f"Terminal container for {chat_id} failed to start within {timeout}s"
        if details:
            msg += f": {details}"
        super().__init__(msg)


class TerminalNotFoundError(TerminalError):
    """Raised when a terminal container is not found."""
    
    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        super().__init__(f"No terminal container found for chat {chat_id}")


class TerminalCapacityError(TerminalError):
    """Raised when maximum container capacity is reached."""
    
    def __init__(self, max_containers: int):
        self.max_containers = max_containers
        super().__init__(f"Maximum container capacity ({max_containers}) reached")


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class TerminalContainer:
    """Metadata for a managed terminal container.
    
    Attributes:
        chat_id: Unique chat/conversation identifier
        container_id: Docker container ID
        container_name: Human-readable container name (e.g., "if-term-abc12345")
        volume_name: Named Docker volume for persistence (e.g., "if-ws-abc12345")
        api_key: Per-container API key for authentication
        internal_url: URL for API calls within Docker network
        status: Current container status ("starting" | "ready" | "stopped" | "error")
        last_accessed: Time of last access for idle tracking (monotonic time)
    """
    chat_id: str
    container_id: str
    container_name: str
    volume_name: str
    api_key: str
    internal_url: str
    status: str = "starting"
    last_accessed: float = 0.0
    
    def touch(self) -> None:
        """Update last_accessed to current monotonic time."""
        self.last_accessed = time.monotonic()
    
    @property
    def idle_seconds(self) -> float:
        """Seconds since last access."""
        return time.monotonic() - self.last_accessed


# ============================================================================
# Global Instance Management
# ============================================================================

_lifecycle_manager: Optional["TerminalLifecycleManager"] = None


def init_lifecycle_manager(
    docker_client: docker.DockerClient,
    config: TerminalConfig,
) -> "TerminalLifecycleManager":
    """Initialize the global lifecycle manager instance.
    
    Args:
        docker_client: Docker SDK client instance
        config: Terminal configuration
        
    Returns:
        The initialized TerminalLifecycleManager
    """
    global _lifecycle_manager
    _lifecycle_manager = TerminalLifecycleManager(docker_client, config)
    return _lifecycle_manager


def get_lifecycle_manager() -> Optional["TerminalLifecycleManager"]:
    """Get the global lifecycle manager instance.
    
    Returns:
        TerminalLifecycleManager if initialized, None otherwise
    """
    return _lifecycle_manager


# ============================================================================
# Lifecycle Manager
# ============================================================================

class TerminalLifecycleManager:
    """Manages the lifecycle of per-chat terminal containers.
    
    Containers use named Docker volumes (not bind mounts) so the filesystem
    at /home/user survives container removal and recreation.
    
    This class is responsible for:
    - Creating containers on demand with named volumes
    - Health checking and readiness polling
    - Tracking container access for idle cleanup
    - Stopping and removing containers (volume persists)
    - Recovering existing containers on application restart
    
    Thread Safety:
        Uses asyncio locks to prevent race conditions when multiple
        coroutines request the same container simultaneously.
    
    Example:
        manager = TerminalLifecycleManager(docker.from_env(), config)
        container = await manager.get_or_create("chat-123")
        # Use container.internal_url for API calls
        await manager.stop("chat-123")  # Volume persists
    """
    
    def __init__(
        self,
        docker_client: docker.DockerClient,
        config: TerminalConfig,
    ):
        """Initialize the lifecycle manager.
        
        Args:
            docker_client: Docker SDK client instance
            config: Terminal configuration
        """
        self._client = docker_client
        self._config = config
        self._containers: dict[str, TerminalContainer] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
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
    
    def _get_hash_suffix(self, chat_id: str) -> str:
        """Generate a short unique suffix from chat ID.
        
        Uses first 8 characters of SHA-256 hash for uniqueness.
        """
        hash_hex = hashlib.sha256(chat_id.encode()).hexdigest()
        return hash_hex[:8]
    
    async def _get_lock(self, chat_id: str) -> asyncio.Lock:
        """Get or create a lock for a chat.
        
        Uses global lock to prevent race conditions in lock creation.
        """
        async with self._global_lock:
            if chat_id not in self._locks:
                self._locks[chat_id] = asyncio.Lock()
            return self._locks[chat_id]
    
    async def get_or_create(self, chat_id: str) -> TerminalContainer:
        """Get an existing container or create a new one.
        
        This is the primary entry point for container access.
        
        Args:
            chat_id: Unique chat/conversation identifier
            
        Returns:
            TerminalContainer with status "ready"
            
        Raises:
            TerminalStartupError: If container fails to start
            TerminalCapacityError: If max container limit reached
        """
        # Check for existing ready container
        existing = self._containers.get(chat_id)
        if existing and existing.status == "ready":
            existing.touch()
            return existing
        
        # Acquire per-chat lock
        lock = await self._get_lock(chat_id)
        async with lock:
            # Double-check after acquiring lock
            existing = self._containers.get(chat_id)
            if existing and existing.status == "ready":
                existing.touch()
                return existing
            
            # Check if a Docker container with that name already exists
            await self._try_adopt_existing_container(chat_id)
            existing = self._containers.get(chat_id)
            if existing and existing.status == "ready":
                existing.touch()
                return existing
            
            # Check capacity
            active_count = sum(1 for c in self._containers.values() if c.status in ("starting", "ready"))
            if active_count >= self._config.max_containers:
                raise TerminalCapacityError(self._config.max_containers)
            
            # Create new container
            container = await self._create_container(chat_id)
            
            # Wait for readiness
            try:
                await self._wait_for_ready(container)
            except TerminalStartupError:
                # Clean up failed container
                self._containers.pop(chat_id, None)
                raise
            
            return container
    
    async def _try_adopt_existing_container(self, chat_id: str) -> None:
        """Try to adopt an existing container from a previous server run.
        
        If container exists and is running, verify health and adopt it.
        If container exists but is stopped, remove it (volume persists).
        """
        suffix = self._get_hash_suffix(chat_id)
        container_name = f"if-term-{suffix}"
        
        loop = asyncio.get_event_loop()
        
        try:
            container = await loop.run_in_executor(
                None,
                lambda: self._client.containers.get(container_name)
            )
        except docker.errors.NotFound:
            return  # No existing container, proceed to create
        except docker.errors.APIError as e:
            logger.warning(f"[Terminal] Error checking for existing container: {e}")
            return
        
        # Check container status
        if container.status == "running":
            # Verify health
            internal_url = f"http://{container_name}:7681"
            try:
                http_client = await self._get_http_client()
                resp = await http_client.get(f"{internal_url}/api/health", timeout=5.0)
                if resp.status_code == 200:
                    # Can't recover API key, so we need to recreate
                    logger.info(f"[Terminal] Found running container {container_name} but cannot recover API key, recreating")
                    await loop.run_in_executor(None, container.stop)
                    await loop.run_in_executor(None, container.remove)
                    return
            except httpx.HTTPError as e:
                logger.warning(f"[Terminal] Existing container health check failed: {e}")
                await loop.run_in_executor(None, container.stop)
                await loop.run_in_executor(None, container.remove)
                return
        else:
            # Container exists but not running, remove it
            logger.info(f"[Terminal] Removing stopped container {container_name}")
            await loop.run_in_executor(None, container.remove)
    
    async def _create_container(self, chat_id: str) -> TerminalContainer:
        """Create a new terminal container with a named volume.
        
        Args:
            chat_id: Unique chat/conversation identifier
            
        Returns:
            TerminalContainer with status "starting"
        """
        suffix = self._get_hash_suffix(chat_id)
        container_name = f"if-term-{suffix}"
        volume_name = f"if-ws-{suffix}"
        api_key = secrets.token_urlsafe(32)
        
        logger.info(f"[Terminal] Creating container {container_name} for chat {chat_id}")
        
        # Run Docker API call in thread pool (it's blocking)
        loop = asyncio.get_event_loop()
        container: Container = await loop.run_in_executor(
            None,
            lambda: self._client.containers.run(
                image=self._config.image,
                name=container_name,
                detach=True,
                environment={
                    "OPEN_TERMINAL_API_KEY": api_key,
                },
                volumes={
                    volume_name: {"bind": "/home/user", "mode": "rw"},
                },
                network=self._config.network,
                mem_limit=self._config.mem_limit,
                cpu_period=100000,
                cpu_quota=self._config.cpu_quota,
                labels={
                    "managed-by": "if-prototype",
                    "chat-id": chat_id,
                },
            )
        )
        
        terminal_container = TerminalContainer(
            chat_id=chat_id,
            container_id=container.id,
            container_name=container_name,
            volume_name=volume_name,
            api_key=api_key,
            internal_url=f"http://{container_name}:7681",
            status="starting",
            last_accessed=time.monotonic(),
        )
        
        self._containers[chat_id] = terminal_container
        
        logger.info(f"[Terminal] Container {container_name} created (ID: {container.id[:12]})")
        
        return terminal_container
    
    async def _wait_for_ready(
        self,
        container: TerminalContainer,
        timeout: Optional[float] = None,
    ) -> None:
        """Wait for container to pass health check.
        
        Polls the /api/health endpoint until it returns 200 or timeout.
        
        Args:
            container: TerminalContainer to check
            timeout: Timeout in seconds (default from config)
            
        Raises:
            TerminalStartupError: If timeout exceeded
        """
        if timeout is None:
            timeout = self._config.startup_timeout
        
        http_client = await self._get_http_client()
        health_url = f"{container.internal_url}/api/health"
        
        logger.debug(f"[Terminal] Waiting for {container.container_name} to be ready...")
        
        start_time = time.monotonic()
        poll_interval = 0.5
        
        while True:
            elapsed = time.monotonic() - start_time
            if elapsed >= timeout:
                container.status = "error"
                raise TerminalStartupError(
                    container.chat_id,
                    timeout,
                    "Health check timeout"
                )
            
            try:
                resp = await http_client.get(health_url)
                if resp.status_code == 200:
                    container.status = "ready"
                    logger.info(f"[Terminal] Container {container.container_name} is ready")
                    return
            except httpx.HTTPError as e:
                logger.debug(f"[Terminal] Health check failed: {e}")
            
            await asyncio.sleep(poll_interval)
    
    async def stop(self, chat_id: str) -> None:
        """Stop and remove a container.
        
        The named volume is preserved for future access.
        
        Args:
            chat_id: Unique chat/conversation identifier
        """
        container = self._containers.get(chat_id)
        if not container:
            return
        
        logger.info(f"[Terminal] Stopping container {container.container_name}")
        
        try:
            # Run Docker operations in thread pool
            loop = asyncio.get_event_loop()
            docker_container = await loop.run_in_executor(
                None,
                lambda: self._client.containers.get(container.container_id)
            )
            await loop.run_in_executor(None, docker_container.stop)
            await loop.run_in_executor(None, docker_container.remove)
        except docker.errors.NotFound:
            logger.debug(f"[Terminal] Container {container.container_name} already removed")
        except docker.errors.APIError as e:
            logger.warning(f"[Terminal] Error stopping container: {e}")
        
        container.status = "stopped"
        del self._containers[chat_id]
    
    async def stop_all(self) -> None:
        """Stop all tracked containers.
        
        Called at application shutdown. Volumes are preserved.
        """
        chat_ids = list(self._containers.keys())
        for cid in chat_ids:
            try:
                await self.stop(cid)
            except Exception as e:
                logger.error(f"[Terminal] Error stopping container for {cid}: {e}")
    
    async def cleanup_idle(self, max_idle_seconds: Optional[int] = None) -> list[str]:
        """Stop containers that have been idle too long.
        
        Args:
            max_idle_seconds: Idle timeout (default from config)
            
        Returns:
            List of chat IDs that were cleaned up
        """
        if max_idle_seconds is None:
            max_idle_seconds = self._config.idle_timeout
        
        cleaned = []
        
        for cid, container in list(self._containers.items()):
            if container.status == "ready" and container.idle_seconds > max_idle_seconds:
                logger.info(
                    f"[Terminal] Cleaning up idle container {container.container_name} "
                    f"(idle for {container.idle_seconds:.0f}s)"
                )
                try:
                    await self.stop(cid)
                    cleaned.append(cid)
                except Exception as e:
                    logger.error(f"[Terminal] Error cleaning up {cid}: {e}")
        
        return cleaned
    
    async def recover_existing(self) -> list[str]:
        """Recover existing managed containers on startup.
        
        Queries Docker for containers with the "managed-by" label
        and either re-adopts or removes them based on health.
        
        Note: Since API keys cannot be recovered, containers are
        stopped and will be recreated on demand. Volumes persist.
        
        Returns:
            List of chat IDs that were found (containers stopped for recreation)
        """
        logger.info("[Terminal] Recovering existing managed containers...")
        
        loop = asyncio.get_event_loop()
        
        try:
            containers = await loop.run_in_executor(
                None,
                lambda: self._client.containers.list(
                    all=True,
                    filters={"label": "managed-by=if-prototype"}
                )
            )
        except docker.errors.APIError as e:
            logger.error(f"[Terminal] Failed to list containers: {e}")
            return []
        
        recovered = []
        
        for container in containers:
            cid = container.labels.get("chat-id")
            if not cid:
                continue
            
            recovered.append(cid)
            
            # Since we can't recover the API key, stop and remove the container
            # The named volume persists, so data is preserved
            logger.info(
                f"[Terminal] Found existing container {container.name} for chat {cid}. "
                "Stopping for recreation (volume persists)."
            )
            
            try:
                if container.status == "running":
                    await loop.run_in_executor(None, container.stop)
                await loop.run_in_executor(None, container.remove)
            except docker.errors.APIError as e:
                logger.warning(f"[Terminal] Error removing container: {e}")
        
        logger.info(f"[Terminal] Recovery complete: {len(recovered)} containers found and stopped")
        return recovered
    
    def get_container(self, chat_id: str) -> Optional[TerminalContainer]:
        """Get container metadata without creating a new one.
        
        Args:
            chat_id: Unique chat/conversation identifier
            
        Returns:
            TerminalContainer if exists and ready, None otherwise
        """
        container = self._containers.get(chat_id)
        if container and container.status == "ready":
            return container
        return None
