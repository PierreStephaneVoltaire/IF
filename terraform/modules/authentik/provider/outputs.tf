output "athletes_role_id" {
  value = authentik_rbac_role.athletes.id
}
output "coaches_role_id" {
  value = authentik_rbac_role.coaches.id
}
output "handlers_role_id" {
  value = authentik_rbac_role.handlers.id
}
output "athletes_group_name" {
  value = authentik_group.athletes.name
}
output "coaches_group_name" {
  value = authentik_group.coaches.name
}
output "handlers_group_name" {
  value = authentik_group.handlers.name
}
output "powerlifting_client_id" {
  value = authentik_provider_oauth2.powerlifting.client_id
}
output "powerlifting_client_secret" {
  value     = authentik_provider_oauth2.powerlifting.client_secret
  sensitive = true
}
output "powerlifting_app_slug" {
  value = authentik_application.powerlifting.slug
}
