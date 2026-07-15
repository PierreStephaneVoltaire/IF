resource "kubernetes_namespace" "if_portals" {
  metadata {
    name = "if-portals"
    labels = {
      app        = "if-ecosystem"
      managed-by = "terraform"
    }
  }
}

resource "kubernetes_persistent_volume_claim" "pl_valkey" {
  metadata {
    name      = "pl-valkey-data"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    labels = {
      app        = "pl-valkey"
      managed-by = "terraform"
    }
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

resource "kubernetes_deployment" "pl_valkey" {
  metadata {
    name      = "pl-valkey"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    labels = {
      app = "pl-valkey"
    }
  }

  spec {
    replicas = 1
    selector {
      match_labels = {
        app = "pl-valkey"
      }
    }
    template {
      metadata {
        labels = {
          app = "pl-valkey"
        }
      }
      spec {
        container {
          name              = "valkey"
          image             = "valkey/valkey:7.2.5"
          image_pull_policy = "IfNotPresent"
          args = [
            "--save", "3600", "1",
            "--appendonly", "no",
            "--maxmemory", "256mb",
            "--maxmemory-policy", "allkeys-lru",
          ]
          port {
            name           = "redis"
            container_port = 6379
          }
          resources {
            limits = {
              memory = "384Mi"
              cpu    = "500m"
            }
            requests = {
              memory = "128Mi"
              cpu    = "100m"
            }
          }
          volume_mount {
            name       = "data"
            mount_path = "/data"
          }
          liveness_probe {
            exec {
              command = ["redis-cli", "ping"]
            }
            initial_delay_seconds = 10
            period_seconds        = 15
            timeout_seconds       = 3
          }
          readiness_probe {
            exec {
              command = ["redis-cli", "ping"]
            }
            initial_delay_seconds = 3
            period_seconds        = 5
            timeout_seconds       = 2
          }
        }
        volume {
          name = "data"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.pl_valkey.metadata[0].name
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "pl_valkey" {
  metadata {
    name      = "pl-valkey"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    labels = {
      app = "pl-valkey"
    }
  }

  spec {
    selector = {
      app = "pl-valkey"
    }
    port {
      name        = "redis"
      port        = 6379
      target_port = 6379
    }
    type = "ClusterIP"
  }
}
