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
provider "kubectl" {
  config_path    = var.kubeconfig_path
  config_context = var.kubeconfig_context
}

locals {
  database_password_effective = random_password.db_password.result
  storage_class_name          = "${var.cluster_name}-local-path"
  app_secret_name             = "${var.cluster_name}-app"

  cluster_manifest = yamlencode({
    apiVersion = "postgresql.cnpg.io/v1"
    kind       = "Cluster"
    metadata = {
      name      = var.cluster_name
      namespace = var.namespace
    }
    spec = {
      instances             = var.instances
      primaryUpdateStrategy = "unsupervised"
      storage = {
        storageClass = local.storage_class_name
        size         = var.storage_size
      }
      bootstrap = {
        initdb = {
          database = var.database
          owner    = var.username
          secret = {
            name = local.app_secret_name
          }
        }
      }
    }
  })
}

resource "kubernetes_storage_class" "local_path" {
  metadata {
    name = local.storage_class_name
  }

  storage_provisioner    = "rancher.io/local-path"
  reclaim_policy         = "Delete"
  volume_binding_mode    = "WaitForFirstConsumer"
  allow_volume_expansion = false
}

resource "random_password" "db_password" {
  length  = 32
  special = false
}

resource "kubernetes_secret" "app_credentials" {
  metadata {
    name      = local.app_secret_name
    namespace = var.namespace
  }
  data = {
    username = var.username
    password = local.database_password_effective
  }
  type = "kubernetes.io/basic-auth"

  lifecycle {
    ignore_changes = [
      metadata[0].annotations,
      metadata[0].labels,
      data,
    ]
  }
}

resource "helm_release" "cnpg_operator" {
  name             = "cnpg"
  repository       = "https://cloudnative-pg.github.io/charts"
  chart            = "cloudnative-pg"
  version          = var.cnpg_chart_version
  namespace        = "cnpg-system"
  create_namespace = true
  set {
    name  = "config.clusterWide"
    value = "true"
  }
}

resource "kubectl_manifest" "cnpg_cluster" {
  yaml_body  = local.cluster_manifest
  depends_on = [helm_release.cnpg_operator, kubernetes_storage_class.local_path, kubernetes_secret.app_credentials]
}
