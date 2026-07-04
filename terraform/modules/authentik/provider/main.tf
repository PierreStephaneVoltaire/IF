provider "authentik" {
  url      = var.authentik_url
  token    = var.authentik_token
  insecure = var.authentik_insecure
}

data "authentik_flow" "default_authorization" {
  slug = "default-provider-authorization-implicit-consent"
}
data "authentik_flow" "default_invalidation" {
  slug = "default-provider-invalidation-flow"
}
data "authentik_flow" "default_authentication" {
  slug = "default-source-authentication"
}

resource "authentik_rbac_role" "athletes" {
  name = "athletes"
}
resource "authentik_rbac_role" "coaches" {
  name = "coaches"
}
resource "authentik_rbac_role" "handlers" {
  name = "handlers"
}

resource "authentik_group" "athletes" {
  name  = "athletes"
  roles = [authentik_rbac_role.athletes.id]
}
resource "authentik_group" "coaches" {
  name  = "coaches"
  roles = [authentik_rbac_role.coaches.id]
}
resource "authentik_group" "handlers" {
  name  = "handlers"
  roles = [authentik_rbac_role.handlers.id]
}

resource "authentik_property_mapping_provider_scope" "powerlifting_groups" {
  name       = "powerlifting-groups"
  scope_name = "groups"
  expression = <<EOT
return {
  "groups": [group.name for group in user.ak_groups.all()],
}
EOT
}

resource "authentik_property_mapping_provider_scope" "powerlifting_roles" {
  name       = "powerlifting-roles"
  scope_name = "roles"
  expression = <<EOT
roles = []
for group in user.ak_groups.all():
    for role in group.roles.all():
        if role.name not in roles:
            roles.append(role.name)
return {
    "roles": roles,
}
EOT
}

resource "authentik_provider_oauth2" "powerlifting" {
  name                = "nolift-powerlifting"
  client_id           = "nolift-powerlifting"
  client_type         = "confidential"
  authorization_flow  = data.authentik_flow.default_authorization.id
  invalidation_flow   = data.authentik_flow.default_invalidation.id
  authentication_flow = data.authentik_flow.default_authentication.id
  signing_key         = "authentik-default"
  property_mappings = [
    authentik_property_mapping_provider_scope.powerlifting_groups.id,
    authentik_property_mapping_provider_scope.powerlifting_roles.id,
  ]
  allowed_redirect_uris = [
    {
      matching_mode = "strict"
      url           = "https://dev.nolift.training/api/auth/callback"
    },
    {
      matching_mode = "strict"
      url           = "http://localhost:3005/api/auth/callback"
    },
  ]
}

resource "authentik_application" "powerlifting" {
  name               = "NoLift Powerlifting"
  slug               = "nolift-powerlifting"
  protocol_provider  = authentik_provider_oauth2.powerlifting.id
  meta_description   = "Powerlifting meet-prep portal (NoLift)"
  policy_engine_mode = "any"
}
