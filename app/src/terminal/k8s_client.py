"""Kubernetes client wrapper for terminal pod management.

This module provides an abstraction layer over the Kubernetes Python client
specifically for terminal pod and PVC operations.

Usage:
    from terminal.k8s_client import K8sTerminalClient, K8sConfig

    k8s_config = K8sConfig.from_env()
    client = K8sTerminalClient(k8s_config)
    client.connect()

    # Create a pod
    pod = client.create_pod(pod_spec)

    # Get pod status
    pod = client.get_pod("if-term-abc123")

    # List pods
    pods = client.list_pods(label_selector="app.kubernetes.io/name=open-terminal")
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, List

from kubernetes import client as k8s_client, config as k8s_config
from kubernetes.client import V1Pod, V1PersistentVolumeClaim, CoreV1Api
from kubernetes.client.exceptions import ApiException

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class K8sConnectionError(Exception):
    """Raised when K8s client connection fails."""
    pass


class K8sResourceNotFoundError(Exception):
    """Raised when a K8s resource is not found."""
    def __init__(self, resource_type: str, name: str, namespace: str):
        self.resource_type = resource_type
        self.name = name
        self.namespace = namespace
        super().__init__(f"{resource_type} '{name}' not found in namespace '{namespace}'")


@dataclass
class K8sConfig:
    """Configuration for Kubernetes client.

    Attributes:
        namespace: Kubernetes namespace for terminal pods
        kubeconfig_path: Optional path to kubeconfig file (None for in-cluster)
    """
    namespace: str = "if-portals"
    kubeconfig_path: Optional[str] = None

    @classmethod
    def from_env(cls) "K8sConfig":
        """Load configuration from environment variables.

        Environment variables:
            K8S_NAMESPACE: Kubernetes namespace (default: if-portals)
            KUBECONFIG: Path to kubeconfig file (optional)

        Returns:
            K8sConfig instance with values from environment
        """
        import os
        return cls(
            namespace=os.getenv("K8S_NAMESPACE", cls.namespace),
            kubeconfig_path=os.getenv("KUBECONFIG") or None,
        )


class K8sTerminalClient:
    """Kubernetes API client for terminal pod management.

    Provides methods for creating, listing, and deleting pods and PVCs
    in the configured namespace.

    Example:
        client = K8sTerminalClient(K8sConfig.from_env())
        client.connect()

        # Create a PVC
        pvc = client.create_pvc(
            name="if-ws-abc123",
            labels={"app": "terminal"},
            storage_class="local-path",
            storage_size="1Gi"
        )

        # Create a pod
        pod = client.create_pod(pod_spec)

        # List pods
        pods = client.list_pods(label_selector="app.kubernetes.io/name=open-terminal")
    """

    def __init__(self, config: K8sConfig):
        """Initialize the K8s client.

        Args:
            config: K8sConfig instance with namespace and connection settings
        """
        self._config = config
        self._api: Optional[CoreV1Api] = None

    def connect(self) -> None:
        """Initialize the Kubernetes client connection.

        Tries in-cluster config first, falls back to kubeconfig file.

        Raises:
            K8sConnectionError: If connection fails
        """
        try:
            if self._config.kubeconfig_path:
                k8s_config.load_kube_config(config_file=self._config.kubeconfig_path)
            else:
                # Try in-cluster config first, fall back to kubeconfig
                try:
                    k8s_config.load_incluster_config()
                    logger.info("[K8s] Using in-cluster configuration")
                except k8s_config.ConfigException:
                    k8s_config.load_kube_config()
                    logger.info("[K8s] Using kubeconfig configuration")
        except Exception as e:
            logger.error(f"[K8s] Failed to load configuration: {e}")
            raise K8sConnectionError(f"Failed to load Kubernetes configuration: {e}")

        self._api = k8s_client.CoreV1Api()
        logger.info(f"[K8s] Connected to namespace: {self._config.namespace}")

    # ===================
    # PVC Operations
    # ===================

    def create_pvc(
        self,
        name: str,
        labels: dict[str, str],
        storage_class: str = "local-path",
        storage_size: str = "1Gi",
    ) -> V1PersistentVolumeClaim:
        """Create a PersistentVolumeClaim.

        Args:
            name: PVC name
            labels: Labels to apply to PVC
            storage_class: StorageClass name
            storage_size: Storage size (e.g., "1Gi")

        Returns:
            Created V1PersistentVolumeClaim object

        Raises:
            ApiException: If PVC creation fails
        """
        pvc = k8s_client.V1PersistentVolumeClaim(
            metadata=k8s_client.V1ObjectMeta(
                name=name,
                namespace=self._config.namespace,
                labels=labels,
            ),
            spec=k8s_client.V1PersistentVolumeClaimSpec(
                access_modes=["ReadWriteOnce"],
                storage_class_name=storage_class,
                resources=k8s_client.V1ResourceRequirements(
                    requests={"storage": storage_size}
                ),
            ),
        )

        return self._api.create_namespaced_persistent_volume_claim(
            namespace=self._config.namespace,
            body=pvc,
        )

    def get_pvc(self, name: str) -> Optional[V1PersistentVolumeClaim]:
        """Get a PVC by name.

        Args:
            name: PVC name

        Returns:
            V1PersistentVolumeClaim if exists, None otherwise
        """
        try:
            return self._api.read_namespaced_persistent_volume_claim(
                name=name,
                namespace=self._config.namespace,
            )
        except ApiException as e:
            if e.status == 404:
                return None
            raise

    def delete_pvc(self, name: str) -> None:
        """Delete a PVC.

        Args:
            name: PVC name

        Raises:
            ApiException: If deletion fails (except 404)
        """
        try:
            self._api.delete_namespaced_persistent_volume_claim(
                name=name,
                namespace=self._config.namespace,
            )
            logger.debug(f"[K8s] Deleted PVC {name}")
        except ApiException as e:
            if e.status != 404:
                raise
            logger.debug(f"[K8s] PVC {name} not found (already deleted)")

    # ===================
    # Pod Operations
    # ===================

    def create_pod(self, pod_spec: dict) -> V1Pod:
        """Create a Pod from a specification dict.

        Args:
            pod_spec: Pod specification as a dictionary

        Returns:
            Created V1Pod object

        Raises:
            ApiException: If pod creation fails
        """
        return self._api.create_namespaced_pod(
            namespace=self._config.namespace,
            body=pod_spec,
        )

    def get_pod(self, name: str) -> Optional[V1Pod]:
        """Get a Pod by name.

        Args:
            name: Pod name

        Returns:
            V1Pod if exists, None otherwise
        """
        try:
            return self._api.read_namespaced_pod(
                name=name,
                namespace=self._config.namespace,
            )
        except ApiException as e:
            if e.status == 404:
                return None
            raise

    def delete_pod(self, name: str, grace_period_seconds: int = 5) -> None:
        """Delete a Pod.

        Args:
            name: Pod name
            grace_period_seconds: Grace period before deletion (default: 5)

        Raises:
            ApiException: If deletion fails (except 404)
        """
        try:
            self._api.delete_namespaced_pod(
                name=name,
                namespace=self._config.namespace,
                grace_period_seconds=grace_period_seconds,
            )
            logger.debug(f"[K8s] Deleted pod {name}")
        except ApiException as e:
            if e.status != 404:
                raise
            logger.debug(f"[K8s] Pod {name} not found (already deleted)")

    def list_pods(self, label_selector: Optional[str] = None) -> List[V1Pod]:
        """List Pods in the namespace.

        Args:
            label_selector: Optional label selector (e.g., "app=terminal")

        Returns:
            List of V1Pod objects
        """
        result = self._api.list_namespaced_pod(
            namespace=self._config.namespace,
            label_selector=label_selector,
        )
        return result.items or []

    def patch_pod(self, name: str, body: dict) -> V1Pod:
        """Patch a Pod.

        Args:
            name: Pod name
            body: Patch body

        Returns:
            Updated V1Pod object

        Raises:
            ApiException: If patch fails
        """
        return self._api.patch_namespaced_pod(
                name=name,
                namespace=self._config.namespace,
                body=body,
            )
