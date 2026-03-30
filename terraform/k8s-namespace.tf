resource "kubernetes_namespace" "if_portals" {
  metadata {
    name = "if-portals"
    labels = {
      app        = "if-ecosystem"
      managed-by = "terraform"
    }
  }
}
