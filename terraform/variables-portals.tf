variable "discord_client_id" {
  description = "Discord Client ID for Powerlifting app"
  type        = string
}

variable "discord_client_secret" {
  description = "Discord Client Secret for Powerlifting app"
  type        = string
  sensitive   = true
}

variable "discord_redirect_uri" {
  description = "Discord Redirect URI for Powerlifting app"
  type        = string
}

variable "jwt_secret" {
  description = "JWT Secret for Powerlifting app"
  type        = string
  sensitive   = true
}

variable "cookie_domain" {
  description = "Cookie domain for Powerlifting app"
  type        = string
  default     = ""
}

variable "cookie_secure" {
  description = "Whether cookie is secure for Powerlifting app"
  type        = string
  default     = "true"
}

variable "directives_discord_client_id" {
  description = "Discord Client ID for Directives portal. Defaults to discord_client_id when empty."
  type        = string
  default     = ""
}

variable "directives_discord_client_secret" {
  description = "Discord Client Secret for Directives portal. Defaults to discord_client_secret when empty."
  type        = string
  sensitive   = true
  default     = ""
}

variable "directives_discord_redirect_uri" {
  description = "Discord Redirect URI for Directives portal. Defaults to the directives portal domain callback when empty."
  type        = string
  default     = ""
}

variable "directives_cookie_domain" {
  description = "Cookie domain for Directives portal. Defaults to the directives portal apex zone when empty."
  type        = string
  default     = ""
}