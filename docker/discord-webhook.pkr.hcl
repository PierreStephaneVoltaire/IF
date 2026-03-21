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

source "docker" "discord_webhook" {
  image    = "public.ecr.aws/docker/library/python:3.12-slim"
  commit   = true
  platform = "linux/amd64"
  changes = [
    "WORKDIR /app",
    "ENV PATH=/root/.local/bin:/usr/local/bin:$PATH",
    "CMD [\"python\", \"-m\", \"uvicorn\", \"src.main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8080\"]"
  ]
}

build {
  name    = "discord-webhook-server"
  sources = ["source.docker.discord_webhook"]

  # Install system dependencies
  provisioner "shell" {
    inline = [
      "apt-get update && apt-get install -y curl ca-certificates",
      "rm -rf /var/lib/apt/lists/*",
      "mkdir -p /app"
    ]
  }

  # Install uv for fast Python package management
  provisioner "shell" {
    inline = [
      "curl -LsSf https://astral.sh/uv/install.sh | sh",
      "export PATH=\"/root/.local/bin:$PATH\"",
      "uv --version"
    ]
  }

  # Copy requirements first for better caching
  provisioner "file" {
    source      = "../app/utils/discord-webhook-server/backend/requirements.txt"
    destination = "/app/requirements.txt"
  }

  # Install Python dependencies using uv
  provisioner "shell" {
    inline = [
      "export PATH=\"/root/.local/bin:$PATH\"",
      "cd /app && uv pip install --system -r requirements.txt"
    ]
  }

  # Copy source code
  provisioner "file" {
    source      = "../app/utils/discord-webhook-server/backend/src"
    destination = "/app/src"
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
