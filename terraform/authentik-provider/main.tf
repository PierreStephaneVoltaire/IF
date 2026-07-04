locals {
  authentik_url = "http://authentik-server.${var.namespace}.svc.cluster.local"
}

provider "authentik" {
  url      = local.authentik_url
  token    = var.authentik_token
  insecure = var.authentik_insecure
}

module "authentik_provider" {
  source = "../modules/authentik/provider"

  authentik_url      = local.authentik_url
  authentik_token    = var.authentik_token
  authentik_insecure = var.authentik_insecure
}