resource "authentik_property_mapping_provider_scope" "verified_discord_subjects" {
  name       = "powerlifting-verified-discord-subjects"
  scope_name = "powerlifting_identity"
  expression = <<EOT
from authentik.sources.oauth.models import UserOAuthSourceConnection
return {
  "discord_subjects": list(UserOAuthSourceConnection.objects.filter(
    user=user, source__provider_type="discord"
  ).values_list("identifier", flat=True)),
}
EOT
}
