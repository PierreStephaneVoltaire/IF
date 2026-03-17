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
  image    = "public.ecr.aws/docker/library/nginx:alpine"
  commit   = true
  platform = "linux/amd64"
  changes = [
    "EXPOSE 80",
    "CMD [\"nginx\", \"-g\", \"daemon off;\"]"
  ]
}

build {
  name    = "portal-frontend"
  sources = ["source.docker.portal_frontend"]

  # Create nginx config for SPA
  provisioner "shell" {
    inline = [
      "mkdir -p /usr/share/nginx/html",
      "cat > /etc/nginx/conf.d/default.conf << 'EOF'\nserver {\n    listen 80;\n    server_name localhost;\n    root /usr/share/nginx/html;\n    index index.html;\n    \n    gzip on;\n    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;\n    \n    location / {\n        try_files $uri $uri/ /index.html;\n    }\n    \n    location /health {\n        access_log off;\n        return 200 \"healthy\";\n        add_header Content-Type text/plain;\n    }\n}\nEOF"
    ]
  }

  # Copy built frontend files
  # Note: Frontend must be built separately before running Packer
  # This expects a pre-built dist/ directory
  provisioner "file" {
    source      = "../app/utils/${var.portal_name}/frontend/dist"
    destination = "/usr/share/nginx/html/"
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
