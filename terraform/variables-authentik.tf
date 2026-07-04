variable "authentik_token" {
  description = "Authentik API token (admin -> Settings -> Tokens)."
  type        = string
  sensitive   = true
  default     = ""
}
