resource "kubernetes_config_map" "tinyauth_config" {
  metadata {
    name      = "tinyauth-config"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  data = {
    TINYAUTH_APPURL          = "https://${var.domain}/auth"
    TINYAUTH_OAUTH_WHITELIST = var.tinyauth_oauth_whitelist
    TINYAUTH_AUTH_USERS      = var.tinyauth_local_users
    TINYAUTH_DATABASE_PATH   = "/data/tinyauth.db"
  }
}

resource "kubernetes_persistent_volume_claim" "tinyauth_data" {
  metadata {
    name      = "tinyauth-data"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = var.storage_class

    resources {
      requests = {
        storage = "1Gi"
      }
    }
  }
}

resource "kubernetes_deployment" "tinyauth" {
  metadata {
    name      = "tinyauth"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    labels = {
      app = "tinyauth"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "tinyauth"
      }
    }

    template {
      metadata {
        labels = {
          app = "tinyauth"
        }
        annotations = {
          "prometheus.io/scrape" = "true"
          "prometheus.io/port"   = "3000"
          "prometheus.io/path"   = "/metrics"
        }
      }

      spec {
        volume {
          name = "data"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.tinyauth_data.metadata[0].name
          }
        }

        container {
          name  = "tinyauth"
          image = "ghcr.io/steveiliop56/tinyauth:${var.tinyauth_image_tag}"

          port {
            container_port = 3000
            name           = "http"
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.tinyauth_config.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.tinyauth_secrets.metadata[0].name
            }
          }

          volume_mount {
            name       = "data"
            mount_path = "/data"
          }

          resources {
            limits = {
              memory = "128Mi"
              cpu    = "100m"
            }
            requests = {
              memory = "64Mi"
              cpu    = "25m"
            }
          }

          liveness_probe {
            http_get {
              path = "/"
              port = 3000
            }
            initial_delay_seconds = 5
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/"
              port = 3000
            }
            initial_delay_seconds = 3
            period_seconds        = 5
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "tinyauth" {
  metadata {
    name      = "tinyauth"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  spec {
    selector = {
      app = "tinyauth"
    }

    port {
      name        = "http"
      port        = 3000
      target_port = 3000
    }

    type = "ClusterIP"
  }
}
