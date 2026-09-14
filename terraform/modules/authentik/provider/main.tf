data "authentik_flow" "default_authorization" {
  slug = "default-provider-authorization-implicit-consent"
}
data "authentik_flow" "default_invalidation" {
  slug = "default-provider-invalidation-flow"
}
data "authentik_flow" "default_source_authentication" {
  slug = "default-source-authentication"
}

# The default self-signed certificate installed by authentik on first boot.
# Used as the signing key for the OAuth2 provider.
data "authentik_certificate_key_pair" "default" {
  name = "authentik Self-signed Certificate"
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

data "authentik_property_mapping_provider_scope" "openid" {
  name = "authentik default OAuth Mapping: OpenID 'openid'"
}
data "authentik_property_mapping_provider_scope" "email" {
  name = "authentik default OAuth Mapping: OpenID 'email'"
}
data "authentik_property_mapping_provider_scope" "profile" {
  name = "authentik default OAuth Mapping: OpenID 'profile'"
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

resource "authentik_source_oauth" "discord" {
  name                = "discord"
  slug                = var.discord_source_slug
  authentication_flow = data.authentik_flow.default_source_authentication.id
  provider_type       = "discord"
  consumer_key        = var.discord_client_id
  consumer_secret     = var.discord_client_secret
  enabled             = true
  user_path_template  = "authentik:%%(username)s"
  group_matching_mode = "name_link"
  user_matching_mode  = "email_link"
  additional_scopes   = "email identify"
  policy_engine_mode  = "any"
}

resource "authentik_provider_oauth2" "powerlifting" {
  name                = "nolift-powerlifting"
  client_id           = "nolift-powerlifting"
  client_type         = "confidential"
  authorization_flow  = data.authentik_flow.default_authorization.id
  invalidation_flow   = data.authentik_flow.default_invalidation.id
  signing_key         = data.authentik_certificate_key_pair.default.id
  grant_types         = ["authorization_code"]
  property_mappings = [
    data.authentik_property_mapping_provider_scope.openid.id,
    data.authentik_property_mapping_provider_scope.email.id,
    data.authentik_property_mapping_provider_scope.profile.id,
    authentik_property_mapping_provider_scope.powerlifting_groups.id,
    authentik_property_mapping_provider_scope.powerlifting_roles.id,
  ]
  allowed_redirect_uris = [
    {
      matching_mode     = "strict"
      url               = "https://dev.nolift.training/api/auth/authentik/callback"
      redirect_uri_type = "authorization"
    },
    {
      matching_mode     = "strict"
      url               = "http://localhost:3005/api/auth/authentik/callback"
      redirect_uri_type = "authorization"
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
