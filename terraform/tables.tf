resource "aws_dynamodb_table" "if_sessions" {
  name         = var.dynamodb_sessions_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Project = "if-prototype-a1"
    Service = "sessions"
  }
}


resource "aws_dynamodb_table" "if_user" {
  name         = var.dynamodb_user_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  tags = {
    Project = "if-prototype-a1"
    Service = "user"
  }
}

resource "aws_dynamodb_table" "if_finance" {
  name         = var.dynamodb_finance_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Project = "if-prototype-a1"
    Service = "finance"
  }
}

resource "aws_dynamodb_table" "if_diary_entries" {
  name         = var.dynamodb_diary_entries_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Project = "if-prototype-a1"
    Service = "diary"
  }
}

resource "aws_dynamodb_table" "if_diary_signals" {
  name         = var.dynamodb_diary_signals_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Project = "if-prototype-a1"
    Service = "diary-signals"
  }
}

resource "aws_dynamodb_table" "if_proposals" {
  name         = var.dynamodb_proposals_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Project = "if-prototype-a1"
    Service = "proposals"
  }
}
resource "aws_dynamodb_table" "if_models" {
  name         = var.dynamodb_models_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Project = "if-prototype-a1"
    Service = "model-registry"
  }
}

resource "aws_dynamodb_table" "if_core" {
  name         = var.dynamodb_core_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Project = "if-prototype-a1"
    Service = "core-directives"
  }
}

resource "aws_dynamodb_table" "if_health" {
  name         = var.dynamodb_health_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Project = "if-prototype-a1"
    Service = "health"
  }
}

resource "aws_dynamodb_table" "if_execution_registry" {
  name         = var.dynamodb_execution_registry_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Project = "if-prototype-a1"
    Service = "agent-execution-registry"
  }
}

resource "aws_dynamodb_table" "if_webhooks" {
  name         = var.dynamodb_webhooks_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Project = "if-prototype-a1"
    Service = "webhooks"
  }
}

resource "aws_dynamodb_table" "if_health_templates" {
  name         = var.dynamodb_templates_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Project = "if-prototype-a1"
    Service = "health-templates"
  }
}

# ─── Powerlifting master competitions ────────────────────────────────────────
# Admin/import-owned. Source of truth for every competition in the catalog.
# Streams NEW_AND_OLD_IMAGES so the master-sync Lambda can fan updates out
# to per-user copies in if-powerlifting-user-competitions.

# ─── Powerlifting user competitions ──────────────────────────────────────────
# Per-user denormalized copies. The Lambda writes master fields here; users
# write the user-owned fields. No streams.

# ─── Powerlifting master federations ─────────────────────────────────────────
# Admin/import-owned catalog. Streams NEW_AND_OLD_IMAGES.

# ─── Powerlifting user federations ───────────────────────────────────────────
# Per-user denormalized copies. No streams.

# ─── Powerlifting goals ──────────────────────────────────────────────────────
# Per-user goals, one row per goal. No program version. No streams.
