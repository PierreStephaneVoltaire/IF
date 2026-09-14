variable "discord_client_id" {
  type      = string
  sensitive = true
}
variable "discord_client_secret" {
  type      = string
  sensitive = true
}
variable "discord_source_slug" {
  type    = string
  default = "discord"
}
