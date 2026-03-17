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

variable "portal_port" {
  type    = string
  default = "3000"
}

source "docker" "portal_backend" {
  image    = "public.ecr.aws/docker/library/node:20-alpine"
  commit   = true
  platform = "linux/amd64"
  changes = [
    "WORKDIR /app",
    "ENV NODE_ENV=production",
    "EXPOSE ${var.portal_port}",
    "CMD [\"node\", \"dist/server.js\"]"
  ]
}

build {
  name    = "portal-backend"
  sources = ["source.docker.portal_backend"]

  # Install build dependencies
  provisioner "shell" {
    inline = [
      "apk add --no-cache curl",
      "mkdir -p /app"
    ]
  }

  # Copy package files
  provisioner "file" {
    source      = "../app/utils/${var.portal_name}/backend/package.json"
    destination = "/app/package.json"
  }

  provisioner "file" {
    source      = "../app/utils/${var.portal_name}/backend/package-lock.json"
    destination = "/app/package-lock.json"
  }

  # Copy shared types if exists
  provisioner "shell" {
    inline = [
      "mkdir -p /app/packages/types"
    ]
  }

  provisioner "file" {
    source      = "../app/utils/${var.portal_name}/packages/types/package.json"
    destination = "/app/packages/types/package.json"
  }

  # Install dependencies
  provisioner "shell" {
    inline = [
      "cd /app && npm ci --include=dev || npm install"
    ]
  }

  # Copy TypeScript config
  provisioner "file" {
    source      = "../app/utils/${var.portal_name}/backend/tsconfig.json"
    destination = "/app/tsconfig.json"
  }

  # Copy source code
  provisioner "file" {
    source      = "../app/utils/${var.portal_name}/backend/src"
    destination = "/app/"
  }

  # Build TypeScript
  provisioner "shell" {
    inline = [
      "cd /app && npm run build"
    ]
  }

  # Create non-root user
  provisioner "shell" {
    inline = [
      "addgroup -g 1001 -S nodejs",
      "adduser -S nodejs -u 1001 -G nodejs",
      "chown -R nodejs:nodejs /app"
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
