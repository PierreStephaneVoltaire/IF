# RBAC resources for terminal pod management

# ServiceAccount for the main API
resource "kubernetes_service_account" "if_agent_api" {
  metadata {
    name      = "if-agent-api"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    labels = {
      app       = "if-agent-api"
      managed-by = "terraform"
    }
  }

  automount_service_account_token = true
}

# Role for terminal pod management (namespace-scoped)
resource "kubernetes_role" "terminal_manager" {
  metadata {
    name      = "terminal-manager"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  # Pod management
  rule {
    api_groups = [""]
    resources  = ["pods"]
    verbs      = ["get", "list", "watch", "create", "delete", "patch"]
  }

  # Pod logs and status
  rule {
    api_groups = [""]
    resources  = ["pods/log", "pods/status"]
    verbs      = ["get"]
  }

  # PVC management
  rule {
    api_groups = [""]
    resources  = ["persistentvolumeclaims"]
    verbs      = ["get", "list", "create", "delete"]
  }
}

# RoleBinding for the terminal manager role
resource "kubernetes_role_binding" "terminal_manager" {
  metadata {
    name      = "terminal-manager"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account.if_agent_api.metadata[0].name
    namespace = kubernetes_namespace.if_portals.metadata[0].name
  }

  role_ref {
    kind      = "Role"
    name      = kubernetes_role.terminal_manager.metadata[0].name
    api_group = "rbac.authorization.k8s.io"
  }
}
