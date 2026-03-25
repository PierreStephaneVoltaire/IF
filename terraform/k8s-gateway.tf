resource "null_resource" "gateway_api_crds" {
  provisioner "local-exec" {
    command = <<-EOT
      kubectl apply --server-side -k github.com/kubernetes-sigs/gateway-api/config/crd?ref=v1.2.0
    EOT
  }
}

resource "kubernetes_namespace" "nginx_gateway" {
  metadata {
    name = "nginx-gateway"
    labels = {
      app        = "nginx-gateway-fabric"
      managed-by = "terraform"
    }
  }
}

resource "helm_release" "nginx_gateway_fabric" {
  name       = "ngf"
  namespace  = kubernetes_namespace.nginx_gateway.metadata[0].name
  repository = "oci://ghcr.io/nginx/charts"
  chart      = "nginx-gateway-fabric"
  version    = "2.0.0"

  set {
    name  = "nginx.service.type"
    value = "LoadBalancer"
  }

  set {
    name  = "nginxGateway.replicas"
    value = "1"
  }

  depends_on = [null_resource.gateway_api_crds]
}

# NGF v2.0.0 chart bug: snippetsFilters.enable helm value doesn't propagate
# the --snippets-filters flag or RBAC. Patch both manually after helm install.
resource "null_resource" "ngf_snippets_enable" {
  depends_on = [helm_release.nginx_gateway_fabric]

  provisioner "local-exec" {
    command = <<-EOT
      kubectl patch clusterrole ngf-nginx-gateway-fabric --type='json' -p='[
        {"op": "add", "path": "/rules/-", "value": {"apiGroups": ["gateway.nginx.org"], "resources": ["snippetsfilters", "snippetspolicies", "ratelimitpolicies", "proxysettingspolicies", "authenticationfilters"], "verbs": ["get", "list", "watch"]}},
        {"op": "add", "path": "/rules/-", "value": {"apiGroups": ["gateway.nginx.org"], "resources": ["snippetsfilters/status", "snippetspolicies/status", "ratelimitpolicies/status", "proxysettingspolicies/status", "authenticationfilters/status"], "verbs": ["update"]}}
      ]' && \
      kubectl patch deployment ngf-nginx-gateway-fabric -n ${kubernetes_namespace.nginx_gateway.metadata[0].name} --type='json' \
        -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--snippets-filters"}]' && \
      kubectl rollout status deployment ngf-nginx-gateway-fabric -n ${kubernetes_namespace.nginx_gateway.metadata[0].name} --timeout=120s
    EOT
  }
}

resource "kubectl_manifest" "gateway" {
  depends_on = [helm_release.nginx_gateway_fabric]

  yaml_body = <<-YAML
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: ${var.gateway_name}
  namespace: ${var.gateway_namespace}
spec:
  gatewayClassName: nginx
  listeners:
    - name: http
      port: 80
      protocol: HTTP
      allowedRoutes:
        namespaces:
          from: All
  YAML
}
