resource "aws_ecr_repository" "if_agent" {
  name                 = "if-agent"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "if_agent" {
  repository = aws_ecr_repository.if_agent.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

locals {
  docker_hash   = filesha1("${path.module}/../docker/build.pkr.hcl")
}

resource "null_resource" "packer_build" {
  triggers = {
    dir_sha1 = local.docker_hash
    repo_url = aws_ecr_repository.if_agent.repository_url
  }

  provisioner "local-exec" {
    working_dir = "${path.module}/../docker"
    command     = <<EOT
      aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws
      packer init build.pkr.hcl
      packer build -var "image_repository=${aws_ecr_repository.if_agent.repository_url}" -var "image_tag=test" build.pkr.hcl
    EOT
  }

  depends_on = [aws_ecr_repository.if_agent]
}
