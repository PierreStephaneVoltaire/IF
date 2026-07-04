locals {
  authentik_domain = "auth.dev.nolift.training"
  authentik_zone   = "nolift.training"
}

module "postgres" {
  source = "./modules/postgres"

  kubeconfig_path    = var.kubeconfig_path
  kubeconfig_context = var.kubeconfig_context
  namespace          = kubernetes_namespace.if_portals.metadata[0].name
}

module "authentik_helm" {
  source = "./modules/authentik/helm"

  kubeconfig_path    = var.kubeconfig_path
  kubeconfig_context = var.kubeconfig_context
  namespace          = kubernetes_namespace.if_portals.metadata[0].name

  postgresql_host     = module.postgres.host
  postgresql_port     = module.postgres.port
  postgresql_database = module.postgres.database
  postgresql_username = module.postgres.username
  postgresql_password = module.postgres.password
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

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Project = "if-prototype-a1"
    Service = "powerlifting-requests"
  }
}
