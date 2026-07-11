# kube-state-metrics service account + RBAC
resource "kubernetes_service_account" "kube_state_metrics" {
  metadata {
    name      = "kube-state-metrics"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
  }
}

resource "kubernetes_cluster_role" "kube_state_metrics" {
  metadata {
    name = "kube-state-metrics"
  }

  rule {
    api_groups = ["*"]
    resources  = ["*"]
    verbs      = ["get", "list", "watch"]
  }
}

resource "kubernetes_cluster_role_binding" "kube_state_metrics" {
  metadata {
    name = "kube-state-metrics"
  }

  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account.kube_state_metrics.metadata[0].name
    namespace = kubernetes_namespace.monitoring.metadata[0].name
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role.kube_state_metrics.metadata[0].name
  }
}

# kube-state-metrics deployment
resource "kubernetes_deployment" "kube_state_metrics" {
  metadata {
    name      = "kube-state-metrics"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
    labels    = { app = "kube-state-metrics" }
  }

  spec {
    replicas = 1
    selector { match_labels = { app = "kube-state-metrics" } }

    template {
      metadata {
        labels = { app = "kube-state-metrics" }
      }

      spec {
        service_account_name = kubernetes_service_account.kube_state_metrics.metadata[0].name

        container {
          name  = "kube-state-metrics"
          image = "registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.12.0"

          port {
            container_port = 8080
            name           = "metrics"
          }

          resources {
            limits = {
              memory = "256Mi"
              cpu    = "250m"
            }
            requests = {
              memory = "64Mi"
              cpu    = "50m"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "kube_state_metrics" {
  metadata {
    name      = "kube-state-metrics"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
    labels    = { app = "kube-state-metrics" }
  }

  spec {
    selector = { app = "kube-state-metrics" }
    port {
      port        = 8080
      target_port = "metrics"
      name        = "metrics"
    }
    type = "ClusterIP"
  }
}

# node-exporter service account
resource "kubernetes_service_account" "node_exporter" {
  metadata {
    name      = "node-exporter"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
  }
}

# node-exporter daemonset
resource "kubernetes_daemon_set_v1" "node_exporter" {
  metadata {
    name      = "node-exporter"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
    labels    = { app = "node-exporter" }
  }

  lifecycle {
    ignore_changes = [
      metadata[0].annotations,
    ]
  }

  spec {
    selector { match_labels = { app = "node-exporter" } }

    template {
      metadata {
        labels = { app = "node-exporter" }
      }

      spec {
        service_account_name = kubernetes_service_account.node_exporter.metadata[0].name
        host_pid             = true
        host_network         = true

        toleration {
          effect   = "NoSchedule"
          operator = "Exists"
        }

        volume {
          name = "proc"
          host_path {
            path = "/proc"
          }
        }

        volume {
          name = "sys"
          host_path {
            path = "/sys"
          }
        }

        volume {
          name = "root"
          host_path {
            path = "/"
          }
        }

        container {
          name  = "node-exporter"
          image = "prom/node-exporter:v1.8.0"
          args = [
            "--path.procfs=/host/proc",
            "--path.sysfs=/host/sys",
            "--path.rootfs=/host/root",
            "--collector.filesystem.ignored-mount-points=^/(sys|proc|dev|host|etc)($$|/)",
          ]

          port {
            container_port = 9100
            name           = "metrics"
            protocol       = "TCP"
          }

          security_context {
            run_as_user = 0
          }

          volume_mount {
            name       = "proc"
            mount_path = "/host/proc"
            read_only  = true
          }

          volume_mount {
            name       = "sys"
            mount_path = "/host/sys"
            read_only  = true
          }

          volume_mount {
            name              = "root"
            mount_path        = "/host/root"
            read_only         = true
            mount_propagation = "HostToContainer"
          }

          resources {
            limits = {
              memory = "128Mi"
              cpu    = "200m"
            }
            requests = {
              memory = "64Mi"
              cpu    = "50m"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "node_exporter" {
  metadata {
    name      = "node-exporter"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
    labels    = { app = "node-exporter" }
  }

  spec {
    selector = { app = "node-exporter" }
    port {
      port        = 9100
      target_port = "metrics"
      name        = "metrics"
    }
    type = "ClusterIP"
  }
}

# cAdvisor service account
resource "kubernetes_service_account" "cadvisor" {
  metadata {
    name      = "cadvisor"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
  }
}

# cAdvisor daemonset
resource "kubernetes_daemon_set_v1" "cadvisor" {
  metadata {
    name      = "cadvisor"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
    labels    = { app = "cadvisor" }
  }

  spec {
    selector { match_labels = { app = "cadvisor" } }

    template {
      metadata {
        labels = { app = "cadvisor" }
      }

      spec {
        service_account_name = kubernetes_service_account.cadvisor.metadata[0].name
        host_pid             = true

        toleration {
          effect   = "NoSchedule"
          operator = "Exists"
        }

        volume {
          name = "rootfs"
          host_path {
            path = "/"
          }
        }

        volume {
          name = "sys"
          host_path {
            path = "/sys"
          }
        }

        volume {
          name = "containerd-sock"
          host_path {
            path = "/run/k3s/containerd/containerd.sock"
            type = "Socket"
          }
        }

        volume {
          name = "containerd-run"
          host_path {
            path = "/run/k3s/containerd"
          }
        }

        container {
          name  = "cadvisor"
          image = "gcr.io/cadvisor/cadvisor:v0.49.1"
          args = [
            "--housekeeping_interval=30s",
            "--docker_only=false",
            "--containerd=/run/containerd/containerd.sock",
            "--disable_metrics=percpu,cpuLoad,cpu_topology,cpuset,disk,diskIO,hugetlb,memory_numa,network,oom_event,perf_event,process,referenced_memory,resctrl,sched,tcp,udp,advtcp",
            "--listen_ip=0.0.0.0",
          ]

          port {
            container_port = 8080
            name           = "metrics"
            protocol       = "TCP"
          }

          security_context {
            privileged = true
          }

          volume_mount {
            name       = "rootfs"
            mount_path = "/rootfs"
            read_only  = true
          }

          volume_mount {
            name       = "sys"
            mount_path = "/sys"
            read_only  = true
          }

          volume_mount {
            name       = "containerd-sock"
            mount_path = "/run/containerd/containerd.sock"
            read_only  = true
          }

          volume_mount {
            name       = "containerd-run"
            mount_path = "/run/containerd"
            read_only  = true
          }

          resources {
            limits = {
              memory = "2Gi"
              cpu    = "500m"
            }
            requests = {
              memory = "256Mi"
              cpu    = "100m"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "cadvisor" {
  metadata {
    name      = "cadvisor"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
    labels    = { app = "cadvisor" }
  }

  spec {
    selector = { app = "cadvisor" }
    port {
      port        = 8080
      target_port = "metrics"
      name        = "metrics"
    }
    type = "ClusterIP"
  }
}
