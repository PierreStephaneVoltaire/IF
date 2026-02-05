# Stoat (Revolt) Self-Hosted Platform Kubernetes Deployment
# Based on https://github.com/revoltchat/self-hosted compose.yml
# This deploys the full Stoat chat platform stack

# ============================================
# CONFIGURATION
# ============================================

locals {
  stoat_namespace = kubernetes_namespace.discord_bot.metadata[0].name
  stoat_domain    = "notdiscord.${var.domain}"

  # Service hostnames (internal DNS)
  mongodb_host = "stoat-mongodb"
  redis_host   = "redis"  # Using existing redis from kubernetes-redis.tf
  rabbit_host  = "stoat-rabbitmq"

  # Generate encryption key if not provided (32 bytes = 44 chars in base64)
  stoat_encryption_key = var.stoat_encryption_key != "" ? var.stoat_encryption_key : base64encode(random_password.stoat_encryption_key[0].result)
}

# Random password resource for generating encryption key
resource "random_password" "stoat_encryption_key" {
  count   = var.stoat_encryption_key == "" ? 1 : 0
  length  = 32
  special = false
}

# ============================================
# SECRETS
# ============================================

resource "kubernetes_secret" "stoat_secrets" {
  metadata {
    name      = "stoat-secrets"
    namespace = local.stoat_namespace
  }

  data = {
    # RabbitMQ credentials
    RABBITMQ_DEFAULT_USER = var.stoat_rabbitmq_user
    RABBITMQ_DEFAULT_PASS = var.stoat_rabbitmq_pass

    # File encryption key (auto-generated if not provided)
    STOAT_ENCRYPTION_KEY = local.stoat_encryption_key

    # VAPID keys for push notifications (generate with generate_config.sh)
    STOAT_VAPID_PRIVATE_KEY = var.stoat_vapid_private_key
    STOAT_VAPID_PUBLIC_KEY  = var.stoat_vapid_public_key
  }

  type = "Opaque"
}

# ============================================
# CONFIGMAP - Revolt.toml
# ============================================

resource "kubernetes_config_map" "stoat_config" {
  metadata {
    name      = "stoat-config"
    namespace = local.stoat_namespace
  }

  data = {
    "Revolt.toml" = <<-EOT
      production = false

      [database]
      mongodb = "mongodb://${local.mongodb_host}:27017"
      redis = "redis://${local.redis_host}:6379"

      [hosts]
      app = "https://${local.stoat_domain}"
      api = "https://${local.stoat_domain}/api"
      events = "wss://${local.stoat_domain}/ws"
      autumn = "https://${local.stoat_domain}/autumn"
      january = "https://${local.stoat_domain}/january"
      voso_legacy = ""
      voso_legacy_ws = ""

      [hosts.livekit]

      [rabbit]
      host = "${local.rabbit_host}"
      port = 5672
      username = "${var.stoat_rabbitmq_user}"
      password = "${var.stoat_rabbitmq_pass}"

      [api]

      [api.registration]
      invite_only = false

      [api.smtp]
      host = ""
      username = ""
      password = ""
      from_address = "noreply@example.com"
      port = 587

      [api.security]
      authifier_shield_key = ""
      voso_legacy_token = ""
      trust_cloudflare = false
      easypwned = ""
      tenor_key = ""

      [api.security.captcha]
      hcaptcha_key = ""
      hcaptcha_sitekey = ""

      [api.workers]
      max_concurrent_connections = 50

      [api.livekit]
      call_ring_duration = 30

      [api.livekit.nodes]

      [api.users]

      [pushd]
      production = true
      mass_mention_chunk_size = 200
      exchange = "revolt.notifications"
      message_queue = "notifications.origin.message"
      mass_mention_queue = "notifications.origin.mass_mention"
      fr_accepted_queue = "notifications.ingest.fr_accepted"
      fr_received_queue = "notifications.ingest.fr_received"
      dm_call_queue = "notifications.ingest.dm_call"
      generic_queue = "notifications.ingest.generic"
      ack_queue = "notifications.process.ack"

      [pushd.vapid]
      queue = "notifications.outbound.vapid"
      private_key = "${var.stoat_vapid_private_key}"
      public_key = "${var.stoat_vapid_public_key}"

      [pushd.fcm]
      queue = "notifications.outbound.fcm"
      key_type = ""
      project_id = ""
      private_key_id = ""
      private_key = ""
      client_email = ""
      client_id = ""
      auth_uri = ""
      token_uri = ""
      auth_provider_x509_cert_url = ""
      client_x509_cert_url = ""

      [pushd.apn]
      sandbox = false
      queue = "notifications.outbound.apn"
      pkcs8 = ""
      key_id = ""
      team_id = ""

      [files]
      encryption_key = "${local.stoat_encryption_key}"
      webp_quality = 80.0
      blocked_mime_types = []
      clamav_host = ""
      scan_mime_types = [
        "application/vnd.microsoft.portable-executable",
        "application/vnd.android.package-archive",
        "application/zip",
      ]

      [files.limit]
      min_file_size = 1
      min_resolution = [1, 1]
      max_mega_pixels = 40
      max_pixel_side = 10000

      [files.preview]
      attachments = [1280, 1280]
      avatars = [128, 128]
      backgrounds = [1280, 720]
      icons = [128, 128]
      banners = [480, 480]
      emojis = [128, 128]

      [files.s3]
      endpoint = "https://s3.${var.region}.amazonaws.com"
      path_style_buckets = false
      region = "${var.region}"
      access_key_id = "${var.aws_access_key}"
      secret_access_key = "${var.aws_secret_key}"
      default_bucket = "${aws_s3_bucket.stoat_uploads.bucket}"

      [features]
    EOT
  }
}

# ============================================
# MONGODB
# ============================================

resource "kubernetes_persistent_volume_claim" "stoat_mongodb_data" {
  metadata {
    name      = "stoat-mongodb-data"
    namespace = local.stoat_namespace
  }

  spec {
    access_modes = ["ReadWriteOnce"]
    resources {
      requests = {
        storage = "10Gi"
      }
    }
    storage_class_name = "do-block-storage"
  }
}

resource "kubernetes_deployment" "stoat_mongodb" {
  metadata {
    name      = "stoat-mongodb"
    namespace = local.stoat_namespace
    labels = {
      app = "stoat-mongodb"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "stoat-mongodb"
      }
    }

    template {
      metadata {
        labels = {
          app = "stoat-mongodb"
        }
      }

      spec {
        node_selector = {
          "workload-type" = "general"
        }

        toleration {
          key      = "dedicated"
          operator = "Equal"
          value    = "general"
          effect   = "NoSchedule"
        }

        container {
          name  = "mongodb"
          image = "public.ecr.aws/docker/library/mongo:7"

          port {
            container_port = 27017
            name           = "mongodb"
          }

          volume_mount {
            name       = "mongodb-data"
            mount_path = "/data/db"
          }

          resources {
            requests = {
              memory = "512Mi"
              cpu    = "250m"
            }
            limits = {
              memory = "2Gi"
              cpu    = "1000m"
            }
          }

          liveness_probe {
            exec {
              command = ["mongosh", "--eval", "db.adminCommand('ping')", "--quiet"]
            }
            initial_delay_seconds = 30
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 5
          }

          readiness_probe {
            exec {
              command = ["mongosh", "--eval", "db.adminCommand('ping')", "--quiet"]
            }
            initial_delay_seconds = 5
            period_seconds        = 5
            timeout_seconds       = 3
            failure_threshold     = 3
          }
        }

        volume {
          name = "mongodb-data"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.stoat_mongodb_data.metadata[0].name
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "stoat_mongodb" {
  metadata {
    name      = "stoat-mongodb"
    namespace = local.stoat_namespace
    labels = {
      app = "stoat-mongodb"
    }
  }

  spec {
    type = "ClusterIP"

    selector = {
      app = "stoat-mongodb"
    }

    port {
      port        = 27017
      target_port = 27017
      name        = "mongodb"
    }
  }
}

# ============================================
# RABBITMQ
# ============================================

resource "kubernetes_persistent_volume_claim" "stoat_rabbitmq_data" {
  metadata {
    name      = "stoat-rabbitmq-data"
    namespace = local.stoat_namespace
  }

  spec {
    access_modes = ["ReadWriteOnce"]
    resources {
      requests = {
        storage = "5Gi"
      }
    }
    storage_class_name = "do-block-storage"
  }
}

resource "kubernetes_deployment" "stoat_rabbitmq" {
  metadata {
    name      = "stoat-rabbitmq"
    namespace = local.stoat_namespace
    labels = {
      app = "stoat-rabbitmq"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "stoat-rabbitmq"
      }
    }

    template {
      metadata {
        labels = {
          app = "stoat-rabbitmq"
        }
      }

      spec {
        node_selector = {
          "workload-type" = "general"
        }

        toleration {
          key      = "dedicated"
          operator = "Equal"
          value    = "general"
          effect   = "NoSchedule"
        }

        container {
          name  = "rabbitmq"
          image = "public.ecr.aws/docker/library/rabbitmq:4"

          port {
            container_port = 5672
            name           = "amqp"
          }

          port {
            container_port = 15672
            name           = "management"
          }

          env {
            name = "RABBITMQ_DEFAULT_USER"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.stoat_secrets.metadata[0].name
                key  = "RABBITMQ_DEFAULT_USER"
              }
            }
          }

          env {
            name = "RABBITMQ_DEFAULT_PASS"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.stoat_secrets.metadata[0].name
                key  = "RABBITMQ_DEFAULT_PASS"
              }
            }
          }

          volume_mount {
            name       = "rabbitmq-data"
            mount_path = "/var/lib/rabbitmq"
          }

          resources {
            requests = {
              memory = "512Mi"
              cpu    = "250m"
            }
            limits = {
              memory = "1Gi"
              cpu    = "500m"
            }
          }

          liveness_probe {
            exec {
              command = ["rabbitmq-diagnostics", "-q", "ping"]
            }
            initial_delay_seconds = 20
            period_seconds        = 10
            timeout_seconds       = 10
            failure_threshold     = 3
          }

          readiness_probe {
            exec {
              command = ["rabbitmq-diagnostics", "-q", "ping"]
            }
            initial_delay_seconds = 20
            period_seconds        = 10
            timeout_seconds       = 10
            failure_threshold     = 3
          }
        }

        volume {
          name = "rabbitmq-data"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.stoat_rabbitmq_data.metadata[0].name
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "stoat_rabbitmq" {
  metadata {
    name      = "stoat-rabbitmq"
    namespace = local.stoat_namespace
    labels = {
      app = "stoat-rabbitmq"
    }
  }

  spec {
    type = "ClusterIP"

    selector = {
      app = "stoat-rabbitmq"
    }

    port {
      port        = 5672
      target_port = 5672
      name        = "amqp"
    }

    port {
      port        = 15672
      target_port = 15672
      name        = "management"
    }
  }
}

# ============================================
# API SERVER
# ============================================

resource "kubernetes_deployment" "stoat_api" {
  metadata {
    name      = "stoat-api"
    namespace = local.stoat_namespace
    labels = {
      app = "stoat-api"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "stoat-api"
      }
    }

    template {
      metadata {
        labels = {
          app = "stoat-api"
        }
      }

      spec {
        node_selector = {
          "workload-type" = "general"
        }

        toleration {
          key      = "dedicated"
          operator = "Equal"
          value    = "general"
          effect   = "NoSchedule"
        }

        container {
          name  = "api"
          image = "ghcr.io/revoltchat/server:20250930-2"

          port {
            container_port = 14702
            name           = "api"
          }

          volume_mount {
            name       = "stoat-config"
            mount_path = "/Revolt.toml"
            sub_path   = "Revolt.toml"
          }

          resources {
            requests = {
              memory = "512Mi"
              cpu    = "250m"
            }
            limits = {
              memory = "2Gi"
              cpu    = "1000m"
            }
          }

          liveness_probe {
            http_get {
              path = "/"
              port = 14702
            }
            initial_delay_seconds = 30
            period_seconds        = 10
            failure_threshold     = 3
          }

          readiness_probe {
            http_get {
              path = "/"
              port = 14702
            }
            initial_delay_seconds = 5
            period_seconds        = 5
            failure_threshold     = 3
          }
        }

        volume {
          name = "stoat-config"
          config_map {
            name = kubernetes_config_map.stoat_config.metadata[0].name
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_deployment.stoat_mongodb,
    kubernetes_deployment.stoat_rabbitmq,
    kubernetes_stateful_set.redis,
  ]
}

resource "kubernetes_service" "stoat_api" {
  metadata {
    name      = "stoat-api"
    namespace = local.stoat_namespace
    labels = {
      app = "stoat-api"
    }
  }

  spec {
    type = "ClusterIP"

    selector = {
      app = "stoat-api"
    }

    port {
      port        = 14702
      target_port = 14702
      name        = "api"
    }
  }
}

# ============================================
# EVENTS SERVICE (Bonfire)
# ============================================

resource "kubernetes_deployment" "stoat_events" {
  metadata {
    name      = "stoat-events"
    namespace = local.stoat_namespace
    labels = {
      app = "stoat-events"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "stoat-events"
      }
    }

    template {
      metadata {
        labels = {
          app = "stoat-events"
        }
      }

      spec {
        node_selector = {
          "workload-type" = "general"
        }

        toleration {
          key      = "dedicated"
          operator = "Equal"
          value    = "general"
          effect   = "NoSchedule"
        }

        container {
          name  = "events"
          image = "ghcr.io/revoltchat/bonfire:20250930-2"

          port {
            container_port = 14703
            name           = "events"
          }

          volume_mount {
            name       = "stoat-config"
            mount_path = "/Revolt.toml"
            sub_path   = "Revolt.toml"
          }

          resources {
            requests = {
              memory = "256Mi"
              cpu    = "100m"
            }
            limits = {
              memory = "1Gi"
              cpu    = "500m"
            }
          }
        }

        volume {
          name = "stoat-config"
          config_map {
            name = kubernetes_config_map.stoat_config.metadata[0].name
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_deployment.stoat_mongodb,
    kubernetes_stateful_set.redis,
  ]
}

resource "kubernetes_service" "stoat_events" {
  metadata {
    name      = "stoat-events"
    namespace = local.stoat_namespace
    labels = {
      app = "stoat-events"
    }
  }

  spec {
    type = "ClusterIP"

    selector = {
      app = "stoat-events"
    }

    port {
      port        = 14703
      target_port = 14703
      name        = "events"
    }
  }
}

# ============================================
# WEB APP (Client)
# ============================================

resource "kubernetes_deployment" "stoat_web" {
  metadata {
    name      = "stoat-web"
    namespace = local.stoat_namespace
    labels = {
      app = "stoat-web"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "stoat-web"
      }
    }

    template {
      metadata {
        labels = {
          app = "stoat-web"
        }
      }

      spec {
        node_selector = {
          "workload-type" = "general"
        }

        toleration {
          key      = "dedicated"
          operator = "Equal"
          value    = "general"
          effect   = "NoSchedule"
        }

        container {
          name  = "web"
          image = "ghcr.io/revoltchat/client:master"

          port {
            container_port = 5000
            name           = "web"
          }

          env {
            name  = "HOSTNAME"
            value = "https://${local.stoat_domain}"
          }

          env {
            name  = "REVOLT_PUBLIC_URL"
            value = "https://${local.stoat_domain}/api"
          }

          resources {
            requests = {
              memory = "128Mi"
              cpu    = "100m"
            }
            limits = {
              memory = "512Mi"
              cpu    = "500m"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "stoat_web" {
  metadata {
    name      = "stoat-web"
    namespace = local.stoat_namespace
    labels = {
      app = "stoat-web"
    }
  }

  spec {
    type = "ClusterIP"

    selector = {
      app = "stoat-web"
    }

    port {
      port        = 5000
      target_port = 5000
      name        = "web"
    }
  }
}

# ============================================
# FILE SERVER (Autumn)
# ============================================

resource "kubernetes_deployment" "stoat_autumn" {
  metadata {
    name      = "stoat-autumn"
    namespace = local.stoat_namespace
    labels = {
      app = "stoat-autumn"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "stoat-autumn"
      }
    }

    template {
      metadata {
        labels = {
          app = "stoat-autumn"
        }
      }

      spec {
        node_selector = {
          "workload-type" = "general"
        }

        toleration {
          key      = "dedicated"
          operator = "Equal"
          value    = "general"
          effect   = "NoSchedule"
        }

        container {
          name  = "autumn"
          image = "ghcr.io/revoltchat/autumn:20250930-2"

          port {
            container_port = 14704
            name           = "autumn"
          }

          volume_mount {
            name       = "stoat-config"
            mount_path = "/Revolt.toml"
            sub_path   = "Revolt.toml"
          }

          resources {
            requests = {
              memory = "256Mi"
              cpu    = "100m"
            }
            limits = {
              memory = "1Gi"
              cpu    = "500m"
            }
          }
        }

        volume {
          name = "stoat-config"
          config_map {
            name = kubernetes_config_map.stoat_config.metadata[0].name
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_deployment.stoat_mongodb,
    aws_s3_bucket.stoat_uploads,
  ]
}

resource "kubernetes_service" "stoat_autumn" {
  metadata {
    name      = "stoat-autumn"
    namespace = local.stoat_namespace
    labels = {
      app = "stoat-autumn"
    }
  }

  spec {
    type = "ClusterIP"

    selector = {
      app = "stoat-autumn"
    }

    port {
      port        = 14704
      target_port = 14704
      name        = "autumn"
    }
  }
}

# ============================================
# METADATA & IMAGE PROXY (January)
# ============================================

resource "kubernetes_deployment" "stoat_january" {
  metadata {
    name      = "stoat-january"
    namespace = local.stoat_namespace
    labels = {
      app = "stoat-january"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "stoat-january"
      }
    }

    template {
      metadata {
        labels = {
          app = "stoat-january"
        }
      }

      spec {
        node_selector = {
          "workload-type" = "general"
        }

        toleration {
          key      = "dedicated"
          operator = "Equal"
          value    = "general"
          effect   = "NoSchedule"
        }

        container {
          name  = "january"
          image = "ghcr.io/revoltchat/january:20250930-2"

          port {
            container_port = 14705
            name           = "january"
          }

          volume_mount {
            name       = "stoat-config"
            mount_path = "/Revolt.toml"
            sub_path   = "Revolt.toml"
          }

          resources {
            requests = {
              memory = "128Mi"
              cpu    = "100m"
            }
            limits = {
              memory = "512Mi"
              cpu    = "250m"
            }
          }
        }

        volume {
          name = "stoat-config"
          config_map {
            name = kubernetes_config_map.stoat_config.metadata[0].name
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "stoat_january" {
  metadata {
    name      = "stoat-january"
    namespace = local.stoat_namespace
    labels = {
      app = "stoat-january"
    }
  }

  spec {
    type = "ClusterIP"

    selector = {
      app = "stoat-january"
    }

    port {
      port        = 14705
      target_port = 14705
      name        = "january"
    }
  }
}

# ============================================
# CRON DAEMON (Crond)
# ============================================

resource "kubernetes_deployment" "stoat_crond" {
  metadata {
    name      = "stoat-crond"
    namespace = local.stoat_namespace
    labels = {
      app = "stoat-crond"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "stoat-crond"
      }
    }

    template {
      metadata {
        labels = {
          app = "stoat-crond"
        }
      }

      spec {
        node_selector = {
          "workload-type" = "general"
        }

        toleration {
          key      = "dedicated"
          operator = "Equal"
          value    = "general"
          effect   = "NoSchedule"
        }

        container {
          name  = "crond"
          image = "ghcr.io/revoltchat/crond:20250930-2"

          volume_mount {
            name       = "stoat-config"
            mount_path = "/Revolt.toml"
            sub_path   = "Revolt.toml"
          }

          resources {
            requests = {
              memory = "128Mi"
              cpu    = "50m"
            }
            limits = {
              memory = "512Mi"
              cpu    = "250m"
            }
          }
        }

        volume {
          name = "stoat-config"
          config_map {
            name = kubernetes_config_map.stoat_config.metadata[0].name
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_deployment.stoat_mongodb,
  ]
}

# ============================================
# PUSH NOTIFICATION DAEMON (Pushd)
# ============================================

resource "kubernetes_deployment" "stoat_pushd" {
  metadata {
    name      = "stoat-pushd"
    namespace = local.stoat_namespace
    labels = {
      app = "stoat-pushd"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "stoat-pushd"
      }
    }

    template {
      metadata {
        labels = {
          app = "stoat-pushd"
        }
      }

      spec {
        node_selector = {
          "workload-type" = "general"
        }

        toleration {
          key      = "dedicated"
          operator = "Equal"
          value    = "general"
          effect   = "NoSchedule"
        }

        container {
          name  = "pushd"
          image = "ghcr.io/revoltchat/pushd:20250930-2"

          volume_mount {
            name       = "stoat-config"
            mount_path = "/Revolt.toml"
            sub_path   = "Revolt.toml"
          }

          resources {
            requests = {
              memory = "128Mi"
              cpu    = "50m"
            }
            limits = {
              memory = "512Mi"
              cpu    = "250m"
            }
          }
        }

        volume {
          name = "stoat-config"
          config_map {
            name = kubernetes_config_map.stoat_config.metadata[0].name
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_deployment.stoat_mongodb,
    kubernetes_stateful_set.redis,
    kubernetes_deployment.stoat_rabbitmq,
  ]
}

# ============================================
# HTTP ROUTES (Gateway API)
# ============================================

resource "kubectl_manifest" "stoat_api_route" {
  yaml_body = <<-YAML
    apiVersion: gateway.networking.k8s.io/v1
    kind: HTTPRoute
    metadata:
      name: stoat-api-route
      namespace: ${kubernetes_namespace.discord_bot.metadata[0].name}
    spec:
      parentRefs:
      - name: main-gateway
        namespace: nginx-gateway
        sectionName: https-stoat
      hostnames:
      - notdiscord.${var.domain}
      rules:
      - matches:
        - path:
            type: PathPrefix
            value: /api
        filters:
        - type: URLRewrite
          urlRewrite:
            path:
              type: ReplacePrefixMatch
              replacePrefixMatch: /
        backendRefs:
        - name: stoat-api
          port: 14702
  YAML

  depends_on = [kubernetes_service.stoat_api]
}

resource "kubectl_manifest" "stoat_ws_route" {
  yaml_body = <<-YAML
    apiVersion: gateway.networking.k8s.io/v1
    kind: HTTPRoute
    metadata:
      name: stoat-ws-route
      namespace: ${kubernetes_namespace.discord_bot.metadata[0].name}
    spec:
      parentRefs:
      - name: main-gateway
        namespace: nginx-gateway
        sectionName: https-stoat
      hostnames:
      - notdiscord.${var.domain}
      rules:
      - matches:
        - path:
            type: PathPrefix
            value: /ws
        filters:
        - type: URLRewrite
          urlRewrite:
            path:
              type: ReplacePrefixMatch
              replacePrefixMatch: /
        backendRefs:
        - name: stoat-events
          port: 14703
  YAML

  depends_on = [kubernetes_service.stoat_events]
}

resource "kubectl_manifest" "stoat_autumn_route" {
  yaml_body = <<-YAML
    apiVersion: gateway.networking.k8s.io/v1
    kind: HTTPRoute
    metadata:
      name: stoat-autumn-route
      namespace: ${kubernetes_namespace.discord_bot.metadata[0].name}
    spec:
      parentRefs:
      - name: main-gateway
        namespace: nginx-gateway
        sectionName: https-stoat
      hostnames:
      - notdiscord.${var.domain}
      rules:
      - matches:
        - path:
            type: PathPrefix
            value: /autumn
        filters:
        - type: URLRewrite
          urlRewrite:
            path:
              type: ReplacePrefixMatch
              replacePrefixMatch: /
        backendRefs:
        - name: stoat-autumn
          port: 14704
  YAML

  depends_on = [kubernetes_service.stoat_autumn]
}

resource "kubectl_manifest" "stoat_january_route" {
  yaml_body = <<-YAML
    apiVersion: gateway.networking.k8s.io/v1
    kind: HTTPRoute
    metadata:
      name: stoat-january-route
      namespace: ${kubernetes_namespace.discord_bot.metadata[0].name}
    spec:
      parentRefs:
      - name: main-gateway
        namespace: nginx-gateway
        sectionName: https-stoat
      hostnames:
      - notdiscord.${var.domain}
      rules:
      - matches:
        - path:
            type: PathPrefix
            value: /january
        filters:
        - type: URLRewrite
          urlRewrite:
            path:
              type: ReplacePrefixMatch
              replacePrefixMatch: /
        backendRefs:
        - name: stoat-january
          port: 14705
  YAML

  depends_on = [kubernetes_service.stoat_january]
}

# Web route does NOT need URL rewrite - it serves the root path
resource "kubectl_manifest" "stoat_web_route" {
  yaml_body = <<-YAML
    apiVersion: gateway.networking.k8s.io/v1
    kind: HTTPRoute
    metadata:
      name: stoat-web-route
      namespace: ${kubernetes_namespace.discord_bot.metadata[0].name}
    spec:
      parentRefs:
      - name: main-gateway
        namespace: nginx-gateway
        sectionName: https-stoat
      hostnames:
      - notdiscord.${var.domain}
      rules:
      - matches:
        - path:
            type: PathPrefix
            value: /
        backendRefs:
        - name: stoat-web
          port: 5000
  YAML

  depends_on = [kubernetes_service.stoat_web]
}

