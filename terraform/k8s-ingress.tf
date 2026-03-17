# Kubernetes Ingress for k3s (Traefik)

resource "kubernetes_ingress_v1" "if_portals" {
  metadata {
    name      = "if-portals-ingress"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    annotations = {
      "kubernetes.io/ingress.class" = "traefik"
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
                number = 80
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
                number = 80
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
                number = 80
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
                number = 80
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
                number = 80
              }
            }
          }
        }

        # Default - serve main portal frontend at root
        path {
          path      = "/"
          path_type = "Prefix"

          backend {
            service {
              name = kubernetes_service.portal_frontends["main-portal"].metadata[0].name
              port {
                number = 80
              }
            }
          }
        }
      }
    }
  }
}
