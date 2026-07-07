provider "kubernetes" {
  config_path    = var.kubeconfig_path
  config_context = var.kubeconfig_context
}
provider "helm" {
  kubernetes {
    config_path    = var.kubeconfig_path
    config_context = var.kubeconfig_context
  }
}

locals {
  secret_key_effective = random_password.authentik_secret_key.result
}

resource "random_password" "authentik_secret_key" {
  length  = 60
  special = false
}

resource "kubernetes_secret" "authentik_env" {
  metadata {
    name      = "authentik-env"
    namespace = var.namespace
    labels = {
      app = "authentik"
    }
  }
  data = {
    AUTHENTIK_SECRET_KEY           = local.secret_key_effective
    AUTHENTIK_POSTGRESQL__HOST     = var.postgresql_host
    AUTHENTIK_POSTGRESQL__PORT     = tostring(var.postgresql_port)
    AUTHENTIK_POSTGRESQL__NAME     = var.postgresql_database
    AUTHENTIK_POSTGRESQL__USER     = var.postgresql_username
    AUTHENTIK_POSTGRESQL__PASSWORD = var.postgresql_password
  }
  type = "Opaque"
}

resource "helm_release" "authentik" {
  name       = "authentik"
  repository = "https://charts.goauthentik.io"
  chart      = "authentik"
  version    = var.chart_version
  namespace  = var.namespace

  set {
    name  = "authentik.existingSecret.secretName"
    value = kubernetes_secret.authentik_env.metadata[0].name
  }
  set {
    name  = "postgresql.enabled"
    value = "false"
  }
  set {
    name  = "redis.enabled"
    value = "true"
  }
  set {
    name  = "server.replicas"
    value = tostring(var.server_replicas)
  }
  set {
    name  = "worker.replicas"
    value = tostring(var.worker_replicas)
  }

  depends_on = [kubernetes_secret.authentik_env]
}
