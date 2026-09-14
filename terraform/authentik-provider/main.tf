locals {}

provider "kubernetes" {
  config_path = "~/.kube/config"
}

data "kubernetes_secret" "authentik_token" {
  metadata {
    name      = var.authentik_token_secret_name
    namespace = var.namespace
  }
}

data "kubernetes_service" "authentik_server" {
  metadata {
    name      = "authentik-server"
    namespace = var.namespace
  }
}

provider "authentik" {
  url      = "http://${data.kubernetes_service.authentik_server.spec[0].cluster_ip}"
  token    = data.kubernetes_secret.authentik_token.data["token"]
  insecure = var.authentik_insecure
}

module "authentik_provider" {
  source = "../modules/authentik/provider"

  discord_client_id     = var.discord_client_id
  discord_client_secret = var.discord_client_secret
  discord_source_slug   = var.discord_source_slug
}

# Write the OIDC client credentials to a Kubernetes secret so the main stack
# can read them.
resource "kubernetes_secret" "powerlifting_oidc" {
  metadata {
    name      = "authentik-powerlifting-oidc"
    namespace = var.namespace
    labels = {
      app = "authentik"
    }
  }
  data = {
    AUTHENTIK_CLIENT_ID     = module.authentik_provider.powerlifting_client_id
    AUTHENTIK_CLIENT_SECRET = module.authentik_provider.powerlifting_client_secret
  }
  type = "Opaque"
}