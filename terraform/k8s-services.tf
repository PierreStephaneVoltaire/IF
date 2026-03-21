# Kubernetes Services for all applications

# Main API Service
resource "kubernetes_service" "if_agent_api" {
  metadata {
    name      = "if-agent-api"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  spec {
    selector = {
      app = "if-agent-api"
    }

    port {
      port        = 8000
      target_port = 8000
    }

    type = "ClusterIP"
  }
}

# Portal Backend Services
resource "kubernetes_service" "portal_backends" {
  for_each = local.portals

  metadata {
    name      = "${each.key}-backend"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  spec {
    selector = {
      app = "${each.key}-backend"
    }

    port {
      port        = each.value.port
      target_port = each.value.port
    }

    type = "ClusterIP"
  }
}

# Portal Frontend Services
resource "kubernetes_service" "portal_frontends" {
  for_each = local.portals

  metadata {
    name      = "${each.key}-frontend"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  spec {
    selector = {
      app = "${each.key}-frontend"
    }

    port {
      port        = 3001
      target_port = 3001
    }

    type = "ClusterIP"
  }
}

# Discord Webhook Server Service
resource "kubernetes_service" "discord_webhook" {
  metadata {
    name      = "discord-webhook-server"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  spec {
    selector = {
      app = "discord-webhook-server"
    }

    port {
      port        = 8080
      target_port = 8080
    }

    type = "ClusterIP"
  }
}
