resource "aws_dynamodb_table" "chat_history" {
  name         = "chat_history"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "date"
  range_key    = "last_message_timestamp"

  attribute {
    name = "date"
    type = "S"
  }

  attribute {
    name = "last_message_timestamp"
    type = "N"
  }


  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name = "chat_history"
  }
}

resource "aws_dynamodb_table" "discord_sessions" {
  name         = "discord_sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "channel_id"

  attribute {
    name = "channel_id"
    type = "S"
  }

  tags = {
    Name = "discord_sessions"
  }
}

resource "aws_dynamodb_table" "discord_executions" {
  name         = "discord_executions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "execution_id"

  attribute {
    name = "execution_id"
    type = "S"
  }

  attribute {
    name = "channel_id"
    type = "S"
  }

  global_secondary_index {
    name            = "channel_id-index"
    hash_key        = "channel_id"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "discord_executions"
    Environment = "production"
  }
}

resource "aws_dynamodb_table" "discord_messages" {
  name         = "discord-messages"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "channelid"
  range_key    = "sortKey"

  attribute {
    name = "channelid"
    type = "S"
  }

  attribute {
    name = "sortKey"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "discord-messages"
    Environment = "production"
    Description = "Stores agentic execution turn history by thread"
  }
}

# LangGraph Checkpoints Table
# Used by the DynamoDBCheckpointer for checkpointing graph execution state
# Supports replay functionality - stores checkpoints with metadata for failed nodes

resource "aws_dynamodb_table" "langgraph_checkpoints" {
  name         = "langgraph_checkpoints"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  # TTL for automatic cleanup (30 days)
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "langgraph_checkpoints"
    Environment = "production"
    Description = "LangGraph checkpoint storage for execution replay"
  }
}

output "langgraph_checkpoints_table_name" {
  value       = aws_dynamodb_table.langgraph_checkpoints.name
  description = "Name of the langgraph_checkpoints DynamoDB table"
}

output "langgraph_checkpoints_table_arn" {
  value       = aws_dynamodb_table.langgraph_checkpoints.arn
  description = "ARN of the langgraph_checkpoints DynamoDB table"
}

output "discord_messages_table_name" {
  value       = aws_dynamodb_table.discord_messages.name
  description = "Name of the discord-messages DynamoDB table"
}

output "discord_messages_table_arn" {
  value       = aws_dynamodb_table.discord_messages.arn
  description = "ARN of the discord-messages DynamoDB table"
}
