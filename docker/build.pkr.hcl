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

source "docker" "if_agent" {
  image    = "public.ecr.aws/docker/library/python:3.11-slim"
  commit   = true
  platform = "linux/amd64"
  changes = [
    "WORKDIR /app",
    "ENV PATH=/root/.local/bin:/usr/local/bin:$PATH",
    "CMD [\"python\", \"-m\", \"uvicorn\", \"src.main:app\", \"--host\", \"0.0.0.0\", \"port\", \"8000\"]"
  ]
}

build {
  name    = "if-agent-api"
  sources = ["source.docker.if_agent"]

  # Install system dependencies
  provisioner "shell" {
    inline = [
      "apt-get update && apt-get install -y curl unzip ca-certificates git",
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
    source      = "../app/requirements.txt"
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
    source      = "../app/src"
    destination = "/app/"
  }

  # Copy main entry point
  provisioner "file" {
    source      = "../app/main_system_prompt.txt"
    destination = "/app/main_system_prompt.txt"
  }

  # Copy data directory structure
  provisioner "file" {
    source      = "../app/data"
    destination = "/app/"
  }

  # Copy sandbox directory
  provisioner "file" {
    source      = "../app/sandbox"
    destination = "/app/"
  }

  # Clean up unnecessary files
  provisioner "shell" {
    inline = [
      "rm -rf /app/data/memory.json",
      "rm -rf /root/.cache"
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
