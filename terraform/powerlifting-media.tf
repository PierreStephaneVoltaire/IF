data "aws_ssm_parameter" "powerlifting_media_base_url" {
  name = "/powerlifting/media/cloudfront-base-url"
}

data "aws_ssm_parameter" "powerlifting_media_signing_key_pair_id" {
  name = "/powerlifting/media/cloudfront-signing-key-pair-id"
}

data "aws_ssm_parameter" "powerlifting_media_signing_private_key" {
  name            = "/powerlifting/media/cloudfront-signing-private-key"
  with_decryption = true
}

locals {
  powerlifting_media_base_url = nonsensitive(data.aws_ssm_parameter.powerlifting_media_base_url.value)

  portal_media_base_urls = {
    "powerlifting-app" = local.powerlifting_media_base_url
  }
}
