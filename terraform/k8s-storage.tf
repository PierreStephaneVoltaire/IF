resource "kubernetes_persistent_volume_claim" "if_agent_data" {
  metadata {
    name      = "if-agent-data"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    annotations = {
      "volume.kubernetes.io/selected-node" = var.node_name
    }
  }

  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = var.storage_class

    resources {
      requests = {
        storage = "${var.data_storage_gb}Gi"
      }
    }
  }
}

resource "kubernetes_persistent_volume_claim" "if_agent_sandbox" {
  metadata {
    name      = "if-agent-sandbox"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    annotations = {
      "volume.kubernetes.io/selected-node" = var.node_name
    }
  }

  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = var.storage_class

    resources {
      requests = {
        storage = "${var.sandbox_storage_gb}Gi"
      }
    }
  }
}

resource "kubernetes_persistent_volume_claim" "if_agent_conversations" {
  metadata {
    name      = "if-agent-conversations"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    annotations = {
      "volume.kubernetes.io/selected-node" = var.node_name
    }
  }

  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = var.storage_class

    resources {
      requests = {
        storage = "${var.conversations_storage_gb}Gi"
      }
    }
  }
}

resource "kubernetes_persistent_volume_claim" "if_agent_facts" {
  metadata {
    name      = "if-agent-facts"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    annotations = {
      "volume.kubernetes.io/selected-node" = var.node_name
    }
  }

  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = var.storage_class

    resources {
      requests = {
        storage = "${var.facts_storage_gb}Gi"
      }
    }
  }
}
