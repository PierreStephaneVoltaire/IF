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

resource "kubernetes_deployment" "open_terminal" {
  metadata {
    name      = "open-terminal"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    labels = {
      app = "open-terminal"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "open-terminal"
      }
    }

    template {
      metadata {
        labels = {
          app = "open-terminal"
        }
      }

      spec {
        service_account_name = kubernetes_service_account.if_agent_api.metadata[0].name

        image_pull_secrets {
          name = kubernetes_secret.ecr_registry.metadata[0].name
        }

        container {
          name  = "terminal"
          image = var.terminal_image

          port {
            container_port = 7681
            name           = "api"
          }

          env {
            name = "OPEN_TERMINAL_API_KEY"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.if_agent_api_secrets.metadata[0].name
                key  = "TERMINAL_API_KEY"
              }
            }
          }

          resources {
            limits = {
              memory = var.terminal_mem_limit
              cpu    = "${var.terminal_cpu_quota}m"
            }
            requests = {
              memory = "2048Mi"
              cpu    = "1000m"
            }
          }

          volume_mount {
            name       = "terminal-workspace"
            mount_path = "/home/user"
          }

          liveness_probe {
            http_get {
              path = "/api/health"
              port = 7681
            }
            initial_delay_seconds = 10
            period_seconds        = 60
          }

          readiness_probe {
            http_get {
              path = "/api/health"
              port = 7681
            }
            initial_delay_seconds = 5
            period_seconds        = 5
          }
        }

        volume {
          name = "terminal-workspace"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.terminal_workspace.metadata[0].name
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "open_terminal" {
  metadata {
    name      = "open-terminal"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    labels = {
      app = "open-terminal"
    }
  }

  spec {
    selector = {
      app = "open-terminal"
    }

    port {
      port        = 7681
      target_port = 7681
      name        = "api"
    }

    type = "ClusterIP"
  }
}
