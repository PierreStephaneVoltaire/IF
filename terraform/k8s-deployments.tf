# Kubernetes Deployments for all applications

# Main API Deployment
resource "kubernetes_deployment" "if_agent_api" {
  metadata {
    name      = "if-agent-api"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    labels = {
      app = "if-agent-api"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "if-agent-api"
      }
    }

    template {
      metadata {
        labels = {
          app = "if-agent-api"
        }
      }

      spec {
        service_account_name = kubernetes_service_account.if_agent_api.metadata[0].name

        image_pull_secrets {
          name = kubernetes_secret.ecr_registry.metadata[0].name
        }

        # Volume definitions for persistent storage
        volume {
          name = "data-storage"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.if_agent_data.metadata[0].name
          }
        }

        volume {
          name = "sandbox-storage"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.if_agent_sandbox.metadata[0].name
          }
        }

        volume {
          name = "conversations-storage"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.if_agent_conversations.metadata[0].name
          }
        }

        volume {
          name = "facts-storage"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.if_agent_facts.metadata[0].name
          }
        }

        # Mount host AWS credentials - k3s on Ubuntu, no IRSA
        volume {
          name = "aws-credentials"
          host_path {
            path = var.aws_credentials_host_path
            type = "Directory"
          }
        }

        container {
          name              = "api"
          image             = "${aws_ecr_repository.if_agent_api.repository_url}:latest"
          image_pull_policy = "Always"

          port {
            container_port = 8000
          }

          resources {
            limits = {
              memory = "${var.api_memory_mb}Mi"
              cpu    = "${var.api_cpu_millicores}m"
            }
            requests = {
              memory = "512Mi"
              cpu    = "250m"
            }
          }

          # Reference ConfigMap for non-sensitive config
          env_from {
            config_map_ref {
              name = kubernetes_config_map.if_agent_api_config.metadata[0].name
            }
          }

          # Reference Secret for sensitive data
          env_from {
            secret_ref {
              name = kubernetes_secret.if_agent_api_secrets.metadata[0].name
            }
          }

          # Volume mounts for persistent storage (match local dev: CWD = /app/src)
          volume_mount {
            name       = "data-storage"
            mount_path = "/app/src/data"
          }

          volume_mount {
            name       = "sandbox-storage"
            mount_path = "/app/src/sandbox"
          }

          volume_mount {
            name       = "conversations-storage"
            mount_path = "/app/src/data/conversations"
          }

          volume_mount {
            name       = "facts-storage"
            mount_path = "/app/src/data/facts"
          }

          volume_mount {
            name       = "aws-credentials"
            mount_path = "/root/.aws"
            read_only  = true
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 8000
            }
            initial_delay_seconds = 30
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = 8000
            }
            initial_delay_seconds = 5
            period_seconds        = 5
          }
        }
      }
    }
  }

  depends_on = [null_resource.packer_build_main_api]
}

# Portal configurations
locals {
  portals = {
    main-portal = {
      port     = 3000
      has_db   = false
      db_table = null
    }
    finance-portal = {
      port     = 3002
      has_db   = true
      db_table = "if-finance"
    }
    diary-portal = {
      port     = 3003
      has_db   = true
      db_table = "if-diary"
    }
    proposals-portal = {
      port     = 3004
      has_db   = true
      db_table = "if-proposals"
    }
    powerlifting-app = {
      port     = 3005
      has_db   = true
      db_table = "powerlifting"
    }
  }
}

# Portal Backend Deployments
resource "kubernetes_deployment" "portal_backends" {
  for_each = local.portals

  metadata {
    name      = "${each.key}-backend"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    labels = {
      app = "${each.key}-backend"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "${each.key}-backend"
      }
    }

    template {
      metadata {
        labels = {
          app = "${each.key}-backend"
        }
        annotations = {
          "prometheus.io/scrape" = "true"
          "prometheus.io/port"   = tostring(each.value.port)
          "prometheus.io/path"   = "/metrics"
        }
      }

      spec {
        image_pull_secrets {
          name = kubernetes_secret.ecr_registry.metadata[0].name
        }

        # Mount host AWS credentials - k3s on Ubuntu, no IRSA
        volume {
          name = "aws-credentials"
          host_path {
            path = var.aws_credentials_host_path
            type = "Directory"
          }
        }

        container {
          name              = "backend"
          image             = "${aws_ecr_repository.portal_backends["${each.key}-backend"].repository_url}:latest"
          image_pull_policy = "Always"

          port {
            container_port = each.value.port
          }

          resources {
            limits = {
              memory = "${var.portal_memory_mb}Mi"
              cpu    = "${var.portal_cpu_millicores}m"
            }
            requests = {
              memory = "256Mi"
              cpu    = "100m"
            }
          }

          # Reference portal-specific ConfigMap
          env_from {
            config_map_ref {
              name = "${each.key}-config"
            }
          }

          volume_mount {
            name       = "aws-credentials"
            mount_path = "/root/.aws"
            read_only  = true
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = each.value.port
            }
            initial_delay_seconds = 10
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = each.value.port
            }
            initial_delay_seconds = 5
            period_seconds        = 5
          }
        }
      }
    }
  }

  depends_on = [null_resource.packer_build_portal_backends]
}

# Portal Frontend Deployments
resource "kubernetes_deployment" "portal_frontends" {
  for_each = local.portals

  metadata {
    name      = "${each.key}-frontend"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    labels = {
      app = "${each.key}-frontend"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "${each.key}-frontend"
      }
    }

    template {
      metadata {
        labels = {
          app = "${each.key}-frontend"
        }
      }

      spec {
        image_pull_secrets {
          name = kubernetes_secret.ecr_registry.metadata[0].name
        }

        container {
          name              = "frontend"
          image             = "${aws_ecr_repository.portal_frontends["${each.key}-frontend"].repository_url}:latest"
          image_pull_policy = "Always"

          port {
            container_port = 3001
          }

          resources {
            limits = {
              memory = "${var.frontend_memory_mb}Mi"
              cpu    = "${var.frontend_cpu_millicores}m"
            }
            requests = {
              memory = "64Mi"
              cpu    = "50m"
            }
          }

          liveness_probe {
            http_get {
              path = "/"
              port = 3001
            }
            initial_delay_seconds = 10
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/"
              port = 3001
            }
            initial_delay_seconds = 5
            period_seconds        = 5
          }
        }
      }
    }
  }

  depends_on = [
    null_resource.packer_build_portal_frontends,
    kubernetes_deployment.portal_backends,
  ]
}

# =============================================================================
# OpenWebUI Deployment
# =============================================================================

resource "kubernetes_persistent_volume_claim" "open_webui_data" {
  metadata {
    name      = "open-webui-data"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = var.storage_class

    resources {
      requests = {
        storage = "2Gi"
      }
    }
  }
}

resource "kubernetes_deployment" "open_webui" {
  metadata {
    name      = "open-webui"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    labels = {
      app = "open-webui"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "open-webui"
      }
    }

    template {
      metadata {
        labels = {
          app = "open-webui"
        }
      }

      spec {
        volume {
          name = "data-storage"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.open_webui_data.metadata[0].name
          }
        }

        container {
          name              = "webui"
          image             = "ghcr.io/open-webui/open-webui:main"
          image_pull_policy = "Always"

          port {
            container_port = 8080
          }

          resources {
            limits = {
              memory = "1024Mi"
              cpu    = "500m"
            }
            requests = {
              memory = "256Mi"
              cpu    = "100m"
            }
          }

          env {
            name  = "OPENAI_API_BASE_URL"
            value = "http://if-agent-api.${kubernetes_namespace.if_portals.metadata[0].name}.svc.cluster.local:8000/v1"
          }

          env {
            name  = "OPENAI_API_KEY"
            value = "unused"
          }

          env {
            name  = "WEBUI_URL"
            value = "https://${var.domain}/chat"
          }

          env {
            name  = "ENABLE_OLLAMA_API"
            value = "false"
          }

          env {
            name  = "ENABLE_OPENAI_API"
            value = "true"
          }

          volume_mount {
            name       = "data-storage"
            mount_path = "/app/backend/data"
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 8080
            }
            initial_delay_seconds = 30
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = 8080
            }
            initial_delay_seconds = 5
            period_seconds        = 5
          }
        }
      }
    }
  }
}
