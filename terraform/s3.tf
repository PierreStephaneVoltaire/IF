resource "aws_s3_bucket" "artifacts" {
  bucket = var.s3_artifact_bucket

  tags = {
    Name        = "Discord Bot Artifacts"
    Environment = "Production"
    App         = "discord-bot"
  }

  # Allow deletion of non-empty bucket for development ease
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "cleanup_old_threads"
    status = "Enabled"

    filter {
      prefix = "threads/"
    }

    expiration {
      days = 30
    }
  }
}

# ============================================
# STOAT UPLOADS BUCKET
# ============================================

resource "random_id" "stoat_bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "stoat_uploads" {
  bucket = "stoat-revolt-uploads-${random_id.stoat_bucket_suffix.hex}"

  tags = {
    Name        = "Stoat Revolt Uploads"
    Environment = "production"
  }

  # Allow deletion of non-empty bucket for development ease
  force_destroy = true
}

# NOTE: CORS is NOT needed on the S3 bucket!
# Autumn (file server) acts as a proxy - browsers upload to Autumn,
# which then stores files in S3 server-side. Browsers never directly
# access S3, so no CORS configuration is required.

# Block public access - files are served through Autumn, not directly from S3
resource "aws_s3_bucket_public_access_block" "stoat_uploads" {
  bucket = aws_s3_bucket.stoat_uploads.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
