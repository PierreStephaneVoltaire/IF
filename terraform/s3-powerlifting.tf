resource "random_id" "powerlifting_bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "powerlifting_data" {
  bucket = "powerlifting-data-${random_id.powerlifting_bucket_suffix.hex}"

  tags = {
    Name        = "Powerlifting Data Bucket"
    Environment = "production"
    Project     = "powerlifting-portal"
  }
}

resource "aws_s3_bucket_public_access_block" "powerlifting_data_public_block" {
  bucket = aws_s3_bucket.powerlifting_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "powerlifting_data_versioning" {
  bucket = aws_s3_bucket.powerlifting_data.id
  versioning_configuration {
    status = "Enabled"
  }
}
