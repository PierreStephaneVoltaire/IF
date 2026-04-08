# NOTE: terminal_workspace PVC is retained for manual migration.
# The open-terminal deployment and service have been removed; shell access is
# now provided by LocalWorkspace (OpenHands SDK) running inside the agent pod.
resource "kubernetes_persistent_volume_claim" "terminal_workspace" {
  metadata {
    name      = "terminal-workspace"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    labels = {
      app = "open-terminal"
    }
    annotations = {
      "volume.kubernetes.io/selected-node" = var.node_name
    }
  }

  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = var.storage_class

    resources {
      requests = {
        storage = "${var.terminal_storage_gb}Gi"
      }
    }
  }
}
