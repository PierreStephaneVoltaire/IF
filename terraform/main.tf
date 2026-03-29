provider "aws" {
  region = var.region
}

provider "random" {}

# k3s Kubernetes provider configuration
# Uses kubeconfig from the EC2 host where k3s is running
provider "kubernetes" {
  config_path    = var.kubeconfig_path
  config_context = var.kubeconfig_context
}

provider "kubectl" {
  config_path    = var.kubeconfig_path
  config_context = var.kubeconfig_context
}

provider "helm" {
  kubernetes {
    config_path    = var.kubeconfig_path
    config_context = var.kubeconfig_context
  }
}