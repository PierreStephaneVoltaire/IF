resource "kubernetes_namespace" "argocd" {
  metadata {
    name = "argocd"
    labels = {
      app        = "argocd"
      managed-by = "terraform"
    }
  }
}

resource "helm_release" "argocd" {
  name             = "argocd"
  namespace        = kubernetes_namespace.argocd.metadata[0].name
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = "9.5.21"
  create_namespace = false

  values = [<<-YAML
    global:
      domain: argocd.${var.powerlifting_app_domain_suffix}
    crds:
      install: true
      keep: true
    redis:
      enabled: true
    repoServer:
      serviceAccount:
        create: true
    controller:
      metrics:
        enabled: true
    server:
      metrics:
        enabled: true
      service:
        type: ClusterIP
      # Plain HTTP behind the gateway. TLS terminates at Cloudflare.
      insecure: true
    dex:
      enabled: false
    configs:
      cm:
        url: https://kubernetes.default.svc
        dexConfig: ""
        statusbadge.enabled: "true"
        timeout.reconciliation: 30s
      rbac:
        policy.csv: |
          p, role:readonly, applications, get, */*, allow
          g, argocd, role:readonly
      params:
        server.insecure: "true"
      secret:
        # bcrypt of `admin` (cost 10). Replace via the ArgoCD CLI before
        # exposing the UI publicly (see docs/argocd.md).
        admin.password: "$2a$10$rRyZGSppD3oyOE.QM0h6mOiXEzVg1W3G24HcmAvqGkKQR1gC9I.hC"
        admin.passwordMtime: "2026-01-01T00:00:00Z"
  YAML
  ]

  depends_on = [kubernetes_namespace.argocd]
}


resource "kubernetes_secret" "argocd_image_updater_ecr" {
  metadata {
    name      = "argocd-image-updater-ecr"
    namespace = kubernetes_namespace.argocd.metadata[0].name
  }

  data = {
    AWS_ACCESS_KEY_ID     = var.ecr_image_updater_access_key_id
    AWS_SECRET_ACCESS_KEY = var.ecr_image_updater_secret_access_key
    AWS_REGION            = var.region
  }
}

resource "helm_release" "argocd_image_updater" {
  name             = "argocd-image-updater"
  namespace        = kubernetes_namespace.argocd.metadata[0].name
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argocd-image-updater"
  version          = "1.2.2"
  create_namespace = false

  values = [<<-YAML
    config:
      registries:
        - name: ECR
          api_url: https://${var.region}.ecr.amazonaws.com/
          prefix: ${var.region}.dkr.ecr
          default: true
          # Authenticate to ECR using the AWS_ACCESS_KEY_ID /
          # AWS_SECRET_ACCESS_KEY env vars mounted on the image-updater
          # pod from kubernetes_secret.argocd_image_updater_ecr.
          credentials: env
          # Accept only `latest-<7-40 hex sha>` tags that CI pushes, plus
          # the bare `latest` tag.
          allowtags: ^latest-[a-f0-9]{7,40}$
          sort_order: latest-last
        - name: DockerHub
          prefix: docker.io
          default: false
        - name: ghcr
          prefix: ghcr.io
          default: false
    server:
      metrics:
        enabled: true
    env:
      - name: AWS_ACCESS_KEY_ID
        valueFrom:
          secretKeyRef:
            name: argocd-image-updater-ecr
            key: AWS_ACCESS_KEY_ID
      - name: AWS_SECRET_ACCESS_KEY
        valueFrom:
          secretKeyRef:
            name: argocd-image-updater-ecr
            key: AWS_SECRET_ACCESS_KEY
      - name: AWS_REGION
        valueFrom:
          secretKeyRef:
            name: argocd-image-updater-ecr
            key: AWS_REGION
  YAML
  ]

  depends_on = [
    helm_release.argocd,
    kubernetes_secret.argocd_image_updater_ecr,
  ]
}


resource "kubernetes_manifest" "argocd_project_powerlifting" {
  manifest = {
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "AppProject"
    metadata = {
      name      = "powerlifting"
      namespace = kubernetes_namespace.argocd.metadata[0].name
      labels = {
        managed-by = "terraform"
      }
    }
    spec = {
      description = "Powerlifting app — backend & frontend (GitOps via image-updater)"
      sourceRepos = [
        var.discord_ai_bot_repo_url,
      ]
      destinations = [
        {
          namespace = kubernetes_namespace.if_portals.metadata[0].name
          server    = "https://kubernetes.default.svc"
        }
      ]
      clusterResourceWhitelist = [{ group = "*", kind = "*" }]
      namespaceResourceWhitelist = [
        { group = "", kind = "*" },
        { group = "apps", kind = "*" },
        { group = "autoscaling", kind = "*" },
        { group = "networking.k8s.io", kind = "*" },
        { group = "gateway.networking.k8s.io", kind = "*" },
        { group = "gateway.nginx.org", kind = "*" },
      ]
      orphanedResources = { warn = false }
    }
  }

  depends_on = [helm_release.argocd]
}

# ─── Locals ──────────────────────────────────────────────────────────────────
locals {
  powerlifting_backend_image  = data.aws_ecr_repository.powerlifting_backend.repository_url
  powerlifting_frontend_image = data.aws_ecr_repository.powerlifting_frontend.repository_url
}


resource "kubernetes_manifest" "argocd_app_powerlifting" {
  manifest = {
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata = {
      name      = "powerlifting-app"
      namespace = kubernetes_namespace.argocd.metadata[0].name
      labels = {
        managed-by = "terraform"
      }
      annotations = {

        "argocd-image-updater.argoproj.io/image-list" = "backend=${local.powerlifting_backend_image},frontend=${local.powerlifting_frontend_image}"

        "argocd-image-updater.argoproj.io/backend.update-strategy"      = "latest"
        "argocd-image-updater.argoproj.io/backend.allow-tags"           = "regex:^latest-[a-f0-9]{7,40}$"
        "argocd-image-updater.argoproj.io/backend.kustomize.image-name" = local.powerlifting_backend_image

        "argocd-image-updater.argoproj.io/frontend.update-strategy"      = "latest"
        "argocd-image-updater.argoproj.io/frontend.allow-tags"           = "regex:^latest-[a-f0-9]{7,40}$"
        "argocd-image-updater.argoproj.io/frontend.kustomize.image-name" = local.powerlifting_frontend_image

        "argocd-image-updater.argoproj.io/refresh" = "2m0s"

        "notifications.argoproj.io/subscribe.on-deployed.slack" = ""
      }
    }
    spec = {
      project = kubernetes_manifest.argocd_project_powerlifting.manifest.metadata.name

      source = {
        repoURL        = var.discord_ai_bot_repo_url
        targetRevision = "master"
        path           = "utils/powerlifting-app/infra"
        kustomize = {

          images = [
            {
              name    = local.powerlifting_backend_image
              newName = local.powerlifting_backend_image
              newTag  = "latest"
            },
            {
              name    = local.powerlifting_frontend_image
              newName = local.powerlifting_frontend_image
              newTag  = "latest"
            },
          ]
        }
      }

      destination = {
        server    = "https://kubernetes.default.svc"
        namespace = kubernetes_namespace.if_portals.metadata[0].name
      }

      syncPolicy = {
        automated = {
          prune      = true
          selfHeal   = true
          allowEmpty = false
        }
        syncOptions = [
          "CreateNamespace=false",
          "PrunePropagationPolicy=foreground",
          "PruneLast=true",
          "ServerSideApply=true",
          "RespectIgnoreDifferences=true",
        ]
        retry = {
          limit = 5
          backoff = {
            duration    = "10s"
            factor      = "2"
            maxDuration = "3m"
          }
        }
      }

      revisionHistoryLimit = 10
    }
  }

  depends_on = [
    kubernetes_manifest.argocd_project_powerlifting,
    helm_release.argocd_image_updater,
  ]
}
