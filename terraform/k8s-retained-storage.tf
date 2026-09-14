resource "kubernetes_namespace" "fission" {
  count = 1

  metadata {
    name = "fission"
    labels = {
      app        = "fission"
      managed-by = "terraform"
    }
  }
}

removed {
  from = helm_release.fission

  lifecycle {
    destroy = false
  }
}
