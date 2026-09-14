locals {
  secret_key_effective = random_password.authentik_secret_key.result

  # The Django shell script that get_or_create's the API token for the
  # akadmin user.  Idempotent — safe on both fresh and existing installs.
  # If the token already exists it prints the existing key; if not it
  # creates one with intent="api" and expiring=False.
  bootstrap_script = <<-EOT
    import os, sys, django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "authentik.root.settings")
    django.setup()
    from authentik.core.models import User, Token

    user, created = User.objects.get_or_create(
        username="akadmin",
        defaults={
            "email": os.environ.get("AUTHENTIK_BOOTSTRAP_EMAIL", "root@example.com"),
            "name": "authentik Default Admin",
            "is_superuser": True,
        },
    )
    if created:
        user.set_password(os.environ.get("AUTHENTIK_BOOTSTRAP_PASSWORD", "authentik"))
        user.save()

    token, tok_created = Token.objects.get_or_create(
        identifier="terraform-provider",
        user=user,
        defaults={"intent": "api", "expiring": False},
    )
    if tok_created:
        token.key = os.environ["AUTHENTIK_BOOTSTRAP_TOKEN"]
        token.save()

    print("TOKEN:" + token.key)
  EOT
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

    # Bootstrap — read by the worker on first startup to create the akadmin
    # user and an API token usable by the authentik Terraform provider stack.
    AUTHENTIK_BOOTSTRAP_EMAIL    = var.bootstrap_email
    AUTHENTIK_BOOTSTRAP_PASSWORD = var.bootstrap_password
    AUTHENTIK_BOOTSTRAP_TOKEN    = var.bootstrap_token
  }
  type = "Opaque"
}

# Secret that stores the API token for the authentik-provider Terraform stack.
# The bootstrap job writes the token here after creating it in authentik's DB.
resource "kubernetes_secret" "authentik_terraform_token" {
  metadata {
    name      = "authentik-terraform-token"
    namespace = var.namespace
    labels = {
      app = "authentik"
    }
  }
  data = {
    token = var.bootstrap_token
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

# Kubernetes Job that runs the authentik Django shell to create the API token
# for the akadmin user.  Idempotent — uses get_or_create so it's safe on both
# fresh and existing installs.  The job runs inside the authentik server pod
# image with the same env (envFrom authentik-env secret) so it can reach the
# database.  The terraform-provider token identifier matches what the
# authentik-provider stack reads from the authentik-terraform-token secret.
resource "kubernetes_job" "bootstrap_token" {
  metadata {
    name      = "authentik-bootstrap-token"
    namespace = var.namespace
    labels = {
      app = "authentik"
    }
  }

  spec {
    # Run once on each apply — the script is idempotent so re-runs are safe.
    backoff_limit = 4
    template {
      metadata {
        labels = {
          app = "authentik"
        }
      }
      spec {
        restart_policy = "Never"
        container {
          name    = "bootstrap"
          image   = "ghcr.io/goauthentik/server:${var.chart_version}"
          command = ["python", "/manage.py", "shell", "-c", local.bootstrap_script]
          env_from {
            secret_ref {
              name = kubernetes_secret.authentik_env.metadata[0].name
            }
          }
        }
      }
    }
  }

  # The job needs the authentik env secret and the helm release to be done
  # (so the DB migrations have run).  We also depend on the token secret so
  # that if it's ever recreated the job re-runs.
  depends_on = [
    kubernetes_secret.authentik_env,
    kubernetes_secret.authentik_terraform_token,
    helm_release.authentik,
  ]
}
