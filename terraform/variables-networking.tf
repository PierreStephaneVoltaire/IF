variable "domain" {
  description = "Primary domain for the cluster (Tailscale MagicDNS or custom domain)"
  type        = string
  default     = ""
}

variable "cloudflare_api_token" {
  description = "Scoped Cloudflare API token (Zone:DNS:Edit, Tunnel:Edit, Access:Edit)"
  type        = string
  sensitive   = true
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID"
  type        = string
}

variable "cloudflare_tunnel_name" {
  description = "Name for the Cloudflare Tunnel"
  type        = string
  default     = "if-tunnel"
}

variable "cloudflare_team_name" {
  description = "Cloudflare Access team name (<team>.cloudflareaccess.com)"
  type        = string
}

variable "cloudflare_zone_plan" {
  description = "Cloudflare zone plan for managed zones (free, pro, business)"
  type        = string
  default     = "free"
}

variable "gateway_name" {
  description = "Name of the manually-managed Gateway resource"
  type        = string
  default     = "nginx-gateway"
}

variable "gateway_namespace" {
  description = "Namespace of the manually-managed Gateway resource"
  type        = string
  default     = "default"
}

variable "tinyauth_secret" {
  description = "Tinyauth session secret (min 32 chars)"
  type        = string
  sensitive   = true
}

variable "google_oauth_client_id" {
  description = "Google OAuth client ID from Google Cloud Console"
  type        = string
  sensitive   = true
}

variable "google_oauth_client_secret" {
  description = "Google OAuth client secret from Google Cloud Console"
  type        = string
  sensitive   = true
}

variable "tinyauth_oauth_whitelist" {
  description = "Comma-separated list of allowed Google email addresses"
  type        = string
  default     = ""
}

variable "tinyauth_local_users" {
  description = "Local users in format 'username:bcrypt_hash' (comma-separated for multiple)"
  type        = string
  default     = ""
}

variable "tinyauth_image_tag" {
  description = "Tinyauth container image tag"
  type        = string
  default     = "v5"
}