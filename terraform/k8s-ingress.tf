# Kubernetes Ingress for k3s (Traefik)

# Traefik Middleware to strip path prefixes for backend API routing
resource "null_resource" "traefik_strip_prefix_middleware" {
  depends_on = [kubernetes_namespace.if_portals]

  provisioner "local-exec" {
    command = <<-EOT
      kubectl apply -f - <<EOF
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: strip-prefix
  namespace: ${kubernetes_namespace.if_portals.metadata[0].name}
spec:
  stripPrefix:
    prefixes:
      - /api
      - /main
      - /finance
      - /diary
      - /proposals
      - /fitness
EOF
    EOT
  }
}

# Traefik Middleware to strip /app/xxx prefixes for frontend routing
resource "null_resource" "traefik_strip_frontend_prefix_middleware" {
  depends_on = [kubernetes_namespace.if_portals]

  provisioner "local-exec" {
    command = <<-EOT
      kubectl apply -f - <<EOF
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: strip-frontend-prefix
  namespace: ${kubernetes_namespace.if_portals.metadata[0].name}
spec:
  stripPrefix:
    prefixes:
      - /app/main
      - /app/finance
      - /app/diary
      - /app/proposals
      - /app/fitness
EOF
    EOT
  }
}

# Ingress for backend APIs with strip-prefix middleware
resource "kubernetes_ingress_v1" "if_portals_backends" {
  depends_on = [null_resource.traefik_strip_prefix_middleware]

  metadata {
    name      = "if-portals-backends-ingress"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    annotations = {
      "kubernetes.io/ingress.class"                      = "traefik"
      "traefik.ingress.kubernetes.io/router.middlewares" = "if-portals-strip-prefix@kubernetescrd"
    }
  }

  spec {
    # Main API
    rule {
      http {
        path {
          path      = "/api"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service.if_agent_api.metadata[0].name
              port {
                number = 8000
              }
            }
          }
        }
      }
    }

    # Portal Backends - route by path prefix
    rule {
      http {
        path {
          path      = "/main"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service.portal_backends["main-portal"].metadata[0].name
              port {
                number = 3000
              }
            }
          }
        }

        path {
          path      = "/finance"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service.portal_backends["finance-portal"].metadata[0].name
              port {
                number = 3002
              }
            }
          }
        }

        path {
          path      = "/diary"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service.portal_backends["diary-portal"].metadata[0].name
              port {
                number = 3003
              }
            }
          }
        }

        path {
          path      = "/proposals"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service.portal_backends["proposals-portal"].metadata[0].name
              port {
                number = 3004
              }
            }
          }
        }

        path {
          path      = "/fitness"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service.portal_backends["powerlifting-app"].metadata[0].name
              port {
                number = 3005
              }
            }
          }
        }
      }
    }
  }
}

# Ingress for frontends with strip-frontend-prefix middleware
resource "kubernetes_ingress_v1" "if_portals_frontends" {
  depends_on = [null_resource.traefik_strip_frontend_prefix_middleware]

  metadata {
    name      = "if-portals-frontends-ingress"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    annotations = {
      "kubernetes.io/ingress.class"                      = "traefik"
      "traefik.ingress.kubernetes.io/router.middlewares" = "if-portals-strip-frontend-prefix@kubernetescrd"
    }
  }

  spec {
    # Portal Frontends - route by path
    rule {
      http {
        path {
          path      = "/app/main"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service.portal_frontends["main-portal"].metadata[0].name
              port {
                number = 3001
              }
            }
          }
        }

        path {
          path      = "/app/finance"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service.portal_frontends["finance-portal"].metadata[0].name
              port {
                number = 3001
              }
            }
          }
        }

        path {
          path      = "/app/diary"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service.portal_frontends["diary-portal"].metadata[0].name
              port {
                number = 3001
              }
            }
          }
        }

        path {
          path      = "/app/proposals"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service.portal_frontends["proposals-portal"].metadata[0].name
              port {
                number = 3001
              }
            }
          }
        }

        path {
          path      = "/app/fitness"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service.portal_frontends["powerlifting-app"].metadata[0].name
              port {
                number = 3001
              }
            }
          }
        }
      }
    }
  }
}

# Main portal frontend at root (no prefix stripping)
resource "kubernetes_ingress_v1" "if_portals_main" {
  metadata {
    name      = "if-portals-main-ingress"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    annotations = {
      "kubernetes.io/ingress.class" = "traefik"
    }
  }

  spec {
    rule {
      http {
        path {
          path      = "/"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service.portal_frontends["main-portal"].metadata[0].name
              port {
                number = 3001
              }
            }
          }
        }
      }
    }
  }
}
