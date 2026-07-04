variable "authentik_token" {
  type      = string
  sensitive = true
  default   = ""
}

variable "namespace" {
  type    = string
  default = "if-portals"
}

variable "authentik_insecure" {
  type    = bool
  default = true
}