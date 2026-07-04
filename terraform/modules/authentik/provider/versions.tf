terraform {
  required_version = ">= 1.7.0"
  required_providers {
    authentik = {
      source  = "goauthentik/authentik"
      version = "~> 2026.5"
    }
  }
}
