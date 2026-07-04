variable "authentik_url" {
  type = string
}
variable "authentik_token" {
  type      = string
  sensitive = true
}
variable "authentik_insecure" {
  type    = bool
  default = true
}
