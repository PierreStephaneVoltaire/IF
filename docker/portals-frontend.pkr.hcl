packer {
  required_plugins {
    docker = {
      version = ">= 1.0.0"
      source  = "github.com/hashicorp/docker"
    }
  }
}

variable "image_repository" {
  type = string
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "portal_name" {
  type    = string
  default = "portal"
}

source "docker" "portal_frontend" {
  image    = "public.ecr.aws/docker/library/node:20-alpine"
  commit   = true
  platform = "linux/amd64"
  changes = [
    "WORKDIR /app",
    "EXPOSE 3001",
    "CMD [\"npx\", \"serve\", \"-s\", \"/app/dist\", \"-l\", \"3001\"]"
  ]
}

build {
  name    = "portal-frontend"
  sources = ["source.docker.portal_frontend"]

  # Install serve for static file serving
  provisioner "shell" {
    inline = [
      "mkdir -p /app/dist",
      "npm install -g serve"
    ]
  }

  # Copy built frontend files
  # Note: Frontend must be built separately before running Packer
  # This expects a pre-built dist/ directory
  provisioner "file" {
    source      = "../app/utils/${var.portal_name}/frontend/dist"
    destination = "/app/dist"
  }

  post-processors {
    post-processor "docker-tag" {
      repository = var.image_repository
      tags       = [var.image_tag, "latest"]
    }
    post-processor "docker-push" {
      ecr_login    = true
      login_server = split("/", var.image_repository)[0]
    }
  }
}
