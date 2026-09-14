locals {
  authentik_domain = "auth.nolift.training"
  authentik_zone   = "nolift.training"
}

module "postgres" {
  source = "./modules/postgres"

  namespace = kubernetes_namespace.if_portals.metadata[0].name
}

module "authentik_helm" {
  source = "./modules/authentik/helm"

  namespace = kubernetes_namespace.if_portals.metadata[0].name

  postgresql_host     = module.postgres.host
  postgresql_port     = module.postgres.port
  postgresql_database = module.postgres.database
  postgresql_username = module.postgres.username
  postgresql_password = module.postgres.password

  bootstrap_email    = var.authentik_bootstrap_email
  bootstrap_password = var.authentik_bootstrap_password
  bootstrap_token    = var.authentik_bootstrap_token
}

resource "cloudflare_record" "authentik_cname" {
  zone_id = cloudflare_zone.managed[local.authentik_zone].id
  name    = local.authentik_domain
  type    = "CNAME"
  content = "${cloudflare_zero_trust_tunnel_cloudflared.this.id}.cfargotunnel.com"
  proxied = true
  comment = "Managed by Terraform — tunnel for authentik"
}

resource "kubectl_manifest" "route_authentik" {
  depends_on = [kubectl_manifest.snippets_security_only]

  yaml_body = <<-YAML
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: authentik
  namespace: ${kubernetes_namespace.if_portals.metadata[0].name}
spec:
  parentRefs:
    - name: ${var.gateway_name}
      namespace: ${var.gateway_namespace}
  hostnames:
    - ${local.authentik_domain}
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      filters:
        - type: ExtensionRef
          extensionRef:
            group: gateway.nginx.org
            kind: SnippetsFilter
            name: security-only
      backendRefs:
        - name: ${module.authentik_helm.server_service_name}
          namespace: ${module.authentik_helm.namespace}
          port: ${module.authentik_helm.server_service_port}
  YAML
}

resource "aws_dynamodb_table" "if_powerlifting_requests" {
  name         = "if-powerlifting-requests"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }

  dynamic "attribute" {
    for_each = toset(["inbox_pk", "inbox_sk", "sent_pk", "sent_sk", "roster_pk", "roster_sk"])
    content {
      name = attribute.value
      type = "S"
    }
  }

  dynamic "global_secondary_index" {
    for_each = { InboxIndex = "inbox", SentIndex = "sent", RosterIndex = "roster" }
    content {
      name            = global_secondary_index.key
      hash_key        = "${global_secondary_index.value}_pk"
      range_key       = "${global_secondary_index.value}_sk"
      projection_type = "ALL"
    }
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Project = "if-prototype-a1"
    Service = "powerlifting-requests"
  }
}
