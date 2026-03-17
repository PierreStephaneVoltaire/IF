"""Kubernetes-based terminal lifecycle manager.

Replaces the Docker-based TerminalLifecycleManager with Kubernetes
pod management while maintaining the same interface.

This module manages the full lifecycle of per-chat terminal pods:
- Creating pods with PVC mounts
- Health checking and readiness polling
- Tracking pod access for idle cleanup
- Stopping and removing pods (PVC persists)
- Recovering existing pods on application restart
- TTL-based cleanup for safety net
- Capacity eviction when max containers reached

Usage:
    from terminal.k8s_lifecycle import K8sTerminalLifecycleManager

    manager = K8sTerminalLifecycleManager(k8s_client, config)

    # Get or create a terminal pod
    container = await manager.get_or_create("chat-123")

    # Use container.internal_url for API calls
    # Execute commands via terminal client

    # Stop and cleanup
    await manager.stop("chat-123")
    await manager.delete_pvc("chat-123")  # Full cleanup
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import httpx
from kubernetes import client as k8s_client
from kubernetes.client import V1Pod

from .config import TerminalConfig
from .k8s_client import K8sTerminalClient

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class K8sTerminalError(Exception):
    """Base exception for K8s terminal errors."""
    pass


class K8sTerminalStartupError(K8sTerminalError):
    """Raised when a terminal pod fails to start within timeout."""

    def __init__(self, chat_id: str, timeout: float, details: str = ""):
        self.chat_id = chat_id
        self.timeout = timeout
        self.details = details
        msg = f"Terminal pod for {chat_id} failed to start within {timeout}s"
        if details:
            msg += f": {details}"
        super().__init__(msg)


class K8sTerminalNotFoundError(K8sTerminalError):
    """Raised when a terminal pod is not found."""

    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        super().__init__(f"No terminal pod found for chat {chat_id}")


class K8sTerminalCapacityError(K8sTerminalError):
    """Raised when maximum pod capacity is reached."""

    def __init__(self, max_containers: int):
        self.max_containers = max_containers
        super().__init__(f"Maximum terminal capacity ({max_containers}) reached")


@dataclass
class K8sTerminalContainer:
    """Metadata for a managed K8s terminal pod.

    Attributes:
        chat_id: Unique chat/conversation identifier
        pod_name: Kubernetes pod name (e.g., "if-term-abc12345")
        pvc_name: PersistentVolumeClaim name (e.g., "if-ws-abc12345")
        api_key: Per-pod API key for authentication
        internal_url: URL for API calls within cluster
        status: Current pod status ("starting" | "ready" | "stopped" | "error")
        last_accessed: Time of last access for idle tracking (monotonic time)
    """
    chat_id: str
    pod_name: str
    pvc_name: str
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


_k8s_lifecycle_manager: Optional["K8sTerminalLifecycleManager"] = None


def init_k8s_lifecycle_manager(
    k8s_client: K8sTerminalClient,
    config: TerminalConfig,
) -> "K8sTerminalLifecycleManager":
    """Initialize the global K8s lifecycle manager instance.

    Args:
        k8s_client: K8s client instance
        config: Terminal configuration

    Returns:
        The initialized K8sTerminalLifecycleManager
    """
    global _k8s_lifecycle_manager
    _k8s_lifecycle_manager = K8sTerminalLifecycleManager(k8s_client, config)
    return _k8s_lifecycle_manager


    return _k8s_lifecycle_manager


def get_k8s_lifecycle_manager() -> Optional["K8sTerminalLifecycleManager"]:
    """Get the global K8s lifecycle manager instance.

    Returns:
        K8sTerminalLifecycleManager if initialized, None otherwise
    """
    return _k8s_lifecycle_manager


class K8sTerminalLifecycleManager:
    """Manages the lifecycle of per-chat terminal pods in Kubernetes.

    Pods use PersistentVolumeClaims (PVCs) for persistent storage
    at /home/user.

    This class is responsible for:
    - Creating pods on demand with PVCs
    - Health checking and readiness polling
    - Tracking pod access for idle cleanup
    - Stopping and removing pods (PVC persists)
    - Recovering existing pods on application restart
    - TTL-based cleanup for safety net
    - Capacity eviction when max containers reached

    Thread Safety:
        Uses asyncio locks to prevent race conditions when multiple
        coroutines request the same pod simultaneously.

    Example:
        manager = K8sTerminalLifecycleManager(k8s_client, config)
        container = await manager.get_or_create("chat-123")
        # Use container.internal_url for API calls
        await manager.stop("chat-123")  # PVC persists
    """

    LABEL_SELECTOR = "app.kubernetes.io/name=open-terminal"
    TTL_ANNOTATION = "if-prototype/ttl-hours"
    DEFAULT_TTL_HOURS = 24

    def __init__(
        self,
        k8s_client: K8sTerminalClient,
        config: TerminalConfig,
    ):
        """Initialize the lifecycle manager.

        Args:
            k8s_client: K8s client instance
            config: Terminal configuration
        """
        self._k8s = k8s_client
        self._config = config
        self._namespace = k8s_client._config.namespace
        self._containers: dict[str, K8sTerminalContainer] = {}
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

    def _build_pod_spec(
        self,
        chat_id: str,
        suffix: str,
        api_key: str,
    ) -> dict:
        """Build the Kubernetes Pod specification.

        Args:
            chat_id: Unique chat/conversation identifier
            suffix: Hash suffix for naming
            api_key: Per-pod API key

        Returns:
            Pod specification as a dictionary
        """
        return {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": f"if-term-{suffix}",
                "namespace": self._namespace,
                "labels": {
                    "app.kubernetes.io/name": "open-terminal",
                    "app.kubernetes.io/instance": f"if-term-{suffix}",
                    "app.kubernetes.io/managed-by": "if-agent-api",
                    "app.kubernetes.io/component": "terminal",
                    "if-prototype/chat-id": chat_id,
                },
                "annotations": {
                    self.TTL_ANNOTATION: str(self.DEFAULT_TTL_HOURS),
                },
            },
            "spec": {
                "containers": [{
                    "name": "terminal",
                    "image": self._config.image,
                    "ports": [{"containerPort": 7681, "name": "api"}],
                    "env": [{"name": "OPEN_TERMINAL_API_KEY", "value": api_key}],
                    "resources": {
                        "limits": {
                            "memory": self._config.mem_limit,
                            "cpu": f"{self._config.cpu_quota}m",
                        },
                        "requests": {
                            "memory": "256Mi",
                            "cpu": "250m",
                        },
                    },
                    "volumeMounts": [{
                        "name": "workspace",
                        "mountPath": "/home/user",
                    }],
                    "livenessProbe": {
                        "httpGet": {"path": "/api/health", "port": 7681},
                        "initialDelaySeconds": 10,
                        "periodSeconds": 30,
                    },
                    "readinessProbe": {
                        "httpGet": {"path": "/api/health", "port": 7681},
                        "initialDelaySeconds": 5,
                        "periodSeconds": 5,
                    },
                }],
                "volumes": [{
                    "name": "workspace",
                    "persistentVolumeClaim": {"claimName": f"if-ws-{suffix}"},
                }],
                "restartPolicy": "Never",
            },
        }

    def _build_pvc_spec(
        self,
        chat_id: str,
        suffix: str,
    ) -> dict:
        """Build the PersistentVolumeClaim specification.

        Args:
            chat_id: Unique chat/conversation identifier
            suffix: Hash suffix for naming

        Returns:
            PVC specification as a dictionary
        """
        return {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {
                "name": f"if-ws-{suffix}",
                "namespace": self._namespace,
                "labels": {
                    "app.kubernetes.io/name": "open-terminal-workspace",
                    "app.kubernetes.io/instance": f"if-ws-{suffix}",
                    "app.kubernetes.io/managed-by": "if-agent-api",
                    "if-prototype/chat-id": chat_id,
                },
            },
            "spec": {
                "accessModes": ["ReadWriteOnce"],
                "storageClassName": self._config.storage_class,
                "resources": {
                    "requests": {
                        "storage": self._config.storage_size,
                    },
                },
            },
        }

    async def get_or_create(self, chat_id: str) -> K8sTerminalContainer:
        """Get an existing container or create a new one.

        This is the primary entry point for container access.

        Args:
            chat_id: Unique chat/conversation identifier

        Returns:
            K8sTerminalContainer with status "ready"

        Raises:
            K8sTerminalStartupError: If pod fails to start
            K8sTerminalCapacityError: If max container limit reached
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

            # Check if a K8s pod with that name already exists
            await self._try_adopt_existing_pod(chat_id)
            existing = self._containers.get(chat_id)
            if existing and existing.status == "ready":
                existing.touch()
                return existing

            # Check capacity with eviction
            await self._check_capacity_with_eviction()

            # Create new pod
            container = await self._create_pod(chat_id)

            # Wait for readiness
            try:
                await self._wait_for_ready(container)
            except K8sTerminalStartupError:
                # Clean up failed pod
                self._containers.pop(chat_id, None)
                raise

            return container

    async def _try_adopt_existing_pod(self, chat_id: str) -> None:
        """Try to adopt an existing K8s pod from a previous run.

        If pod exists and is running with healthy status, adopt it.
        If pod exists but is stopped or unhealthy, delete it (will be recreated).
        """
        suffix = self._get_hash_suffix(chat_id)
        pod_name = f"if-term-{suffix}"

        try:
            pod = self._k8s.get_pod(pod_name)
        except Exception:
            return  # No existing pod, proceed to create

        if not pod:
            return

        # Check pod status
        if pod.status.phase == "Running":
            # Verify health
            internal_url = f"http://{pod.status.pod_ip}:7681"
            try:
                http_client = await self._get_http_client()
                resp = await http_client.get(f"{internal_url}/api/health", timeout=5.0)
                if resp.status_code == 200:
                    # Cannot recover API key from existing pod, so we need to recreate
                    logger.info(
                        f"[Terminal] Found running pod {pod_name} but cannot recover API key, recreating"
                    )
                    await self._k8s.delete_pod(pod_name)
                    return
            except httpx.HTTPError:
                logger.warning(f"[Terminal] Existing pod health check failed, recreating")
                await self._k8s.delete_pod(pod_name)
        else:
            # Pod exists but not running, remove it
            logger.info(f"[Terminal] Removing non-running pod {pod_name}")
            await self._k8s.delete_pod(pod_name)

    async def _check_capacity_with_eviction(self) -> None:
        """Check capacity and evict oldest pod if needed.

        If at or above max containers, evict the oldest pod instead of rejecting.
        """
        pods = self._k8s.list_pods(label_selector=self.LABEL_SELECTOR)

        active_pods = [
            p for p in pods
            if p.status.phase in ("Pending", "Running")
        ]

        active_count = len(active_pods)

        if active_count >= self._config.max_containers:
            # Evict oldest pod
            oldest = min(active_pods, key=lambda p: p.metadata.creation_timestamp)
            oldest_chat_id = oldest.metadata.labels.get("if-prototype/chat-id")

            if not oldest_chat_id:
                logger.warning("[Terminal] Cannot evict pod without chat-id label")
                raise K8sTerminalCapacityError(self._config.max_containers)

            logger.warning(
                f"[Terminal] Capacity reached, evicting oldest pod {oldest.metadata.name}"
            )
            await self.stop(oldest_chat_id)

    async def _create_pod(self, chat_id: str) -> K8sTerminalContainer:
        """Create a new terminal pod with a PVC.

        Args:
            chat_id: Unique chat/conversation identifier

        Returns:
            K8sTerminalContainer with status "starting"
        """
        suffix = self._get_hash_suffix(chat_id)
        pod_name = f"if-term-{suffix}"
        pvc_name = f"if-ws-{suffix}"
        api_key = secrets.token_urlsafe(32)

        logger.info(f"[Terminal] Creating pod {pod_name} for chat {chat_id}")

        # Create PVC first (if not exists)
        try:
            existing_pvc = self._k8s.get_pvc(pvc_name)
            if not existing_pvc:
                pvc_labels = {
                    "app.kubernetes.io/name": "open-terminal-workspace",
                    "app.kubernetes.io/instance": pvc_name,
                    "app.kubernetes.io/managed-by": "if-agent-api",
                    "if-prototype/chat-id": chat_id,
                }
                self._k8s.create_pvc(
                    name=pvc_name,
                    labels=pvc_labels,
                    storage_class=self._config.storage_class,
                    storage_size=self._config.storage_size,
                )
                logger.info(f"[Terminal] Created PVC {pvc_name}")
        except Exception as e:
            logger.warning(f"[Terminal] PVC creation warning: {e}")

        # Create pod
        pod_spec = self._build_pod_spec(chat_id, suffix, api_key)
        pod = self._k8s.create_pod(pod_spec)

        container = K8sTerminalContainer(
            chat_id=chat_id,
            pod_name=pod_name,
            pvc_name=pvc_name,
            api_key=api_key,
            internal_url=f"http://{pod.status.pod_ip}:7681" if pod.status.pod_ip else "",
            status="starting",
            last_accessed=time.monotonic(),
        )

        self._containers[chat_id] = container

        logger.info(f"[Terminal] Pod {pod_name} created")

        return container

    async def _wait_for_ready(
        self,
        container: K8sTerminalContainer,
        timeout: Optional[float] = None,
    ) -> None:
        """Wait for pod to pass health check.

        Polls the /api/health endpoint until it returns 200 or timeout.

        Args:
            container: K8sTerminalContainer to check
            timeout: Timeout in seconds (default from config)

        Raises:
            K8sTerminalStartupError: If timeout exceeded
        """
        if timeout is None:
            timeout = self._config.startup_timeout

        http_client = await self._get_http_client()

        logger.debug(f"[Terminal] Waiting for {container.pod_name} to be ready...")

        start_time = time.monotonic()
        poll_interval = 0.5

        while True:
            elapsed = time.monotonic() - start_time
            if elapsed >= timeout:
                container.status = "error"
                raise K8sTerminalStartupError(
                    container.chat_id,
                    timeout,
                    "Health check timeout"
                )

            # Get pod IP if not set
            if not container.internal_url:
                pod = self._k8s.get_pod(container.pod_name)
                if pod and pod.status.pod_ip:
                    container.internal_url = f"http://{pod.status.pod_ip}:7681"

            # Check health
            if container.internal_url:
                try:
                    resp = await http_client.get(
                        f"{container.internal_url}/api/health",
                        timeout=5.0,
                    )
                    if resp.status_code == 200:
                        container.status = "ready"
                        logger.info(f"[Terminal] Pod {container.pod_name} is ready")
                        return
                except httpx.HTTPError as e:
                    logger.debug(f"[Terminal] Health check failed: {e}")

            await asyncio.sleep(poll_interval)

    async def stop(self, chat_id: str) -> None:
        """Stop and remove a pod.

        The PVC is preserved for future use.

        Args:
            chat_id: Unique chat/conversation identifier
        """
        container = self._containers.get(chat_id)
        if not container:
            return

        logger.info(f"[Terminal] Stopping pod {container.pod_name}")

        try:
            self._k8s.delete_pod(container.pod_name)
        except Exception as e:
            logger.warning(f"[Terminal] Error stopping pod: {e}")

        container.status = "stopped"
        del self._containers[chat_id]

    async def delete_pvc(self, chat_id: str) -> None:
        """Delete PVC for a conversation (full data cleanup).

        Args:
            chat_id: Unique chat/conversation identifier
        """
        suffix = self._get_hash_suffix(chat_id)
        pvc_name = f"if-ws-{suffix}"

        try:
            self._k8s.delete_pvc(pvc_name)
            logger.info(f"[Terminal] Deleted PVC {pvc_name}")
        except Exception as e:
            logger.warning(f"[Terminal] Failed to delete PVC {pvc_name}: {e}")

    async def stop_all(self) -> None:
        """Stop all tracked pods.

        Called at application shutdown. PVCs are preserved.
        """
        chat_ids = list(self._containers.keys())
        for cid in chat_ids:
            try:
                await self.stop(cid)
            except Exception as e:
                logger.error(f"[Terminal] Error stopping pod for {cid}: {e}")

    async def cleanup_idle(self, max_idle_seconds: Optional[int] = None) -> list[str]:
        """Stop pods that have been idle too long.

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
                    f"[Terminal] Cleaning up idle pod {container.pod_name} "
                    f"(idle for {container.idle_seconds:.0f}s)"
                )
                try:
                    await self.stop(cid)
                    cleaned.append(cid)
                except Exception as e:
                    logger.error(f"[Terminal] Error cleaning up {cid}: {e}")

        return cleaned

    async def cleanup_expired_ttls(self) -> list[str]:
        """Clean up pods that exceeded their TTL.

        Checks the TTL annotation on all terminal pods and deletes
        those that have exceeded their TTL.

        Returns:
            List of pod names that were cleaned up
        """
        pods = self._k8s.list_pods(label_selector=self.LABEL_SELECTOR)

        cleaned = []
        now = time.time()

        for pod in pods:
            ttl_hours_str = pod.metadata.annotations.get(self.TTL_ANNOTATION)
            if not ttl_hours_str:
                continue

            try:
                ttl_hours = float(ttl_hours_str)
            except ValueError:
                continue

            # Calculate age in hours
            creation_ts = pod.metadata.creation_timestamp
            if not creation_ts:
                continue

            age_hours = (now - creation_ts) / 3600

            if age_hours > ttl_hours:
                pod_name = pod.metadata.name
                chat_id = pod.metadata.labels.get("if-prototype/chat-id")

                logger.info(
                    f"[Terminal] Pod {pod_name} exceeded TTL ({age_hours:.1f}h > {ttl_hours}h), cleaning up"
                )

                try:
                    self._k8s.delete_pod(pod_name)
                    cleaned.append(pod_name)

                    # Also remove from in-memory tracking
                    if chat_id and chat_id in self._containers:
                        del self._containers[chat_id]
                except Exception as e:
                    logger.error(f"[Terminal] Error cleaning up TTL-expired pod {pod_name}: {e}")

        return cleaned

    async def recover_existing(self) -> list[str]:
        """Recover existing managed pods on startup.

        Queries K8s for pods with the terminal label
        and removes them (cannot recover API key).

        PVCs persist for data preservation.

        Returns:
            List of chat IDs that were found (pods stopped for recreation)
        """
        logger.info("[Terminal] Recovering existing managed pods...")

        try:
            pods = self._k8s.list_pods(label_selector=self.LABEL_SELECTOR)
        except Exception as e:
            logger.error(f"[Terminal] Failed to list pods: {e}")
            return []

        recovered = []

        for pod in pods:
            chat_id = pod.metadata.labels.get("if-prototype/chat-id")
            if not chat_id:
                continue

            recovered.append(chat_id)

            # Since we can't recover the API key, stop and remove the pod
            # The PVC persists, so data is preserved
            logger.info(
                f"[Terminal] Found existing pod {pod.metadata.name} for chat {chat_id}. "
                "Stopping for recreation (PVC persists)."
            )

            try:
                self._k8s.delete_pod(pod.metadata.name)
            except Exception as e:
                logger.warning(f"[Terminal] Error removing pod: {e}")

        logger.info(f"[Terminal] Recovery complete: {len(recovered)} pods found and stopped")
        return recovered

    def get_container(self, chat_id: str) -> Optional[K8sTerminalContainer]:
        """Get container metadata without creating a new one.

        Args:
            chat_id: Unique chat/conversation identifier

        Returns:
            K8sTerminalContainer if exists and ready, None otherwise
        """
        container = self._containers.get(chat_id)
        if container and container.status == "ready":
            return container
        return None
