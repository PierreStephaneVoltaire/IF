resource "random_password" "powerlifting_principal" {
  length  = 64
  special = false
}

resource "random_password" "powerlifting_session" {
  length  = 64
  special = false
}
