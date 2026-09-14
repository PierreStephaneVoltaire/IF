variable "authentik_token_secret_name" {
  description = "Name of the Kubernetes secret (in var.namespace) that contains the authentik API token. Created by the main stack's bootstrap job."
  type        = string
}

variable "namespace" {
  description = "Namespace where authentik is installed by the main stack."
  type        = string
  default     = "if-portals"
}

variable "authentik_insecure" {
  description = "Skip TLS verification when connecting to the in-cluster authentik server."
  type        = bool
  default     = true
}

variable "discord_client_id" {
  description = "Discord OAuth client ID for the social login source."
  type        = string
  sensitive   = true
}

variable "discord_client_secret" {
  description = "Discord OAuth client secret for the social login source."
  type        = string
  sensitive   = true
}

variable "discord_source_slug" {
  description = "Slug for the Discord OAuth source in authentik."
  type        = string
  default     = "discord"
}