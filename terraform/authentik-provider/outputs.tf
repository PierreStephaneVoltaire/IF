output "athletes_role_id" {
  value = module.authentik_provider.athletes_role_id
}

output "coaches_role_id" {
  value = module.authentik_provider.coaches_role_id
}

output "handlers_role_id" {
  value = module.authentik_provider.handlers_role_id
}

output "athletes_group_name" {
  value = module.authentik_provider.athletes_group_name
}

output "coaches_group_name" {
  value = module.authentik_provider.coaches_group_name
}

output "handlers_group_name" {
  value = module.authentik_provider.handlers_group_name
}

output "powerlifting_client_id" {
  value = module.authentik_provider.powerlifting_client_id
}

output "powerlifting_client_secret" {
  value     = module.authentik_provider.powerlifting_client_secret
  sensitive = true
}

output "powerlifting_app_slug" {
  value = module.authentik_provider.powerlifting_app_slug
}