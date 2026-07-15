# ============================================================================
# State-only removals: these resources belong in the powerlifting-app stack
# (utils/powerlifting-app/terraform), not in this main agent stack. They were
# provisionally added here and now need to be removed from THIS stack's state
# so they can be imported into the powerlifting-app stack without collision.
#
# A `removed` block takes the resource out of state without destroying the
# underlying AWS resource. After `terraform apply`, the resources are no
# longer tracked here. They are then `terraform import`-ed into the
# powerlifting-app stack by their AWS ARNs.
# ============================================================================

# ─── DynamoDB tables (were in tables.tf) ─────────────────────────────────────
removed {
  from = aws_dynamodb_table.if_powerlifting_analysis_cache
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_dynamodb_table.if_powerlifting_master_competitions
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_dynamodb_table.if_powerlifting_user_competitions
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_dynamodb_table.if_powerlifting_master_federations
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_dynamodb_table.if_powerlifting_user_federations
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_dynamodb_table.if_powerlifting_goals
  lifecycle {
    destroy = false
  }
}

# ─── S3 bucket (was in s3-powerlifting.tf) ──────────────────────────────────
removed {
  from = aws_s3_bucket.powerlifting_data
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_s3_bucket_public_access_block.powerlifting_data_public_block
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_s3_bucket_server_side_encryption_configuration.powerlifting_data
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_s3_bucket_versioning.powerlifting_data_versioning
  lifecycle {
    destroy = false
  }
}

# Note: random_id.powerlifting_bucket_suffix is intentionally NOT in the
# removed list. It is a deterministic input to the bucket name and is safe
# to keep in this stack's state (it does not exist as an AWS resource). It
# will simply become orphaned in state and can be `terraform state rm`-ed
# separately, or it can be left alone as dead state.

# ─── Powerlifting master-sync Lambda (was in powerlifting-master-sync.tf) ──
removed {
  from = aws_sqs_queue.powerlifting_master_sync_dlq
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_iam_role.powerlifting_master_sync_lambda
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_iam_role_policy.powerlifting_master_sync_lambda
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_lambda_function.powerlifting_master_sync
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_lambda_event_source_mapping.powerlifting_master_competitions
  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_lambda_event_source_mapping.powerlifting_master_federations
  lifecycle {
    destroy = false
  }
}
