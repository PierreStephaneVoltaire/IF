# ─── Authentik bootstrap (first-startup only) ─────────────────────────────────
# These are read by the authentik worker on first startup to create the akadmin
# user and an API token. The token is then used by the authentik-provider stack
# to authenticate the authentik Terraform provider.
variable "authentik_bootstrap_email" {
  description = "Email for the akadmin user created on first startup."
  type        = string
}
variable "authentik_bootstrap_password" {
  description = "Password for the akadmin user created on first startup."
  type        = string
  sensitive   = true
}
variable "authentik_bootstrap_token" {
  description = "API token created for akadmin on first startup. Used by the authentik-provider stack."
  type        = string
  sensitive   = true
}

# ─── Authentik OIDC (created by the authentik-provider stack) ─────────────────
# The authentik-provider stack creates the OIDC provider + application and
# writes the client_id/client_secret to the authentik-powerlifting-oidc
# Kubernetes secret. This stack reads that secret (see k8s-secrets.tf).
