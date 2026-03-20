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
    "CMD [\"node\", \"/app/node_modules/.bin/serve\", \"-s\", \"/app/dist\", \"-l\", \"3001\"]"
  ]
}

build {
  name    = "portal-frontend"
  sources = ["source.docker.portal_frontend"]

  # Install build tools
  provisioner "shell" {
    inline = [
      "apk add --no-cache curl",
      "mkdir -p /workspace /app"
    ]
  }

  # Copy entire portal workspace (needed for npm workspaces + shared types package)
  provisioner "file" {
    source      = "../app/utils/${var.portal_name}/"
    destination = "/workspace"
  }

  # Install all workspace dependencies, build types, then build frontend
  # Supports both npm workspace portals (with packages/types) and standalone frontends
  provisioner "shell" {
    inline = [
      "if [ -f /workspace/package.json ] && grep -q '\"workspaces\"' /workspace/package.json; then cd /workspace && npm ci && npm run build --workspace=packages/types && npm run build --workspace=frontend && cp -r /workspace/frontend/dist /app/dist; else cd /workspace/frontend && npm ci && npm run build && cp -r /workspace/frontend/dist /app/dist; fi",
      "npm install -g serve"
    ]
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
