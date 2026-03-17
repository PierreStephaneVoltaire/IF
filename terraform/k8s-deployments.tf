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

        container {
          name  = "api"
          image = "${aws_ecr_repository.if_agent_api.repository_url}:latest"

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

          env {
            name  = "AWS_REGION"
            value = var.region
          }

          env {
            name  = "AWS_SDK_LOAD_CONFIG"
            value = "true"
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
      }

      spec {
        container {
          name  = "backend"
          image = "${aws_ecr_repository.portal_backends["${each.key}-backend"].repository_url}:latest"

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

          env {
            name  = "PORT"
            value = tostring(each.value.port)
          }

          env {
            name  = "AWS_REGION"
            value = var.region
          }

          env {
            name  = "AWS_SDK_LOAD_CONFIG"
            value = "true"
          }

          dynamic "env" {
            for_each = each.value.has_db ? [1] : []
            content {
              name  = "DYNAMODB_TABLE"
              value = each.value.db_table
            }
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
        container {
          name  = "frontend"
          image = "${aws_ecr_repository.portal_frontends["${each.key}-frontend"].repository_url}:latest"

          port {
            container_port = 80
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
              path = "/health"
              port = 80
            }
            initial_delay_seconds = 5
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/"
              port = 80
            }
            initial_delay_seconds = 2
            period_seconds        = 5
          }
        }
      }
    }
  }
}
