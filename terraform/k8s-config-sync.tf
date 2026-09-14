# Preserve counted state addresses while keeping configuration sync independent of Fission.
locals {
  config_sync_dirs = [
    { src = var.specialists_host_path, dest = "specialists" },
    { src = var.tools_host_path, dest = "tools" },
    { src = var.models_host_path, dest = "models" },
    { src = var.scripts_host_path, dest = "scripts" },
    { src = var.skills_host_path, dest = "skills" },
  ]
}

resource "null_resource" "config_sync_content" {
  count = 1

  triggers = {
    content_sha1 = sha1(join(",", [
      for d in local.config_sync_dirs :
      length(fileset(d.src, "**")) > 0 ? sha1(join(",", [
        for f in fileset(d.src, "**") :
        "${f}=${filemd5("${d.src}/${f}")}"
      ])) : "empty"
    ]))
  }
}

resource "kubernetes_job" "sync_config_pvcs" {
  count = 1

  metadata {
    name      = "sync-config-pvcs"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    labels = {
      app        = "config-sync"
      managed-by = "terraform"
    }
    annotations = {
      "config-sync/content-sha1" = null_resource.config_sync_content[0].triggers["content_sha1"]
    }
  }

  spec {
    ttl_seconds_after_finished = 300
    backoff_limit              = 2
    parallelism                = 1
    completions                = 1

    template {
      metadata {
        labels = {
          app = "config-sync"
        }
      }

      spec {
        restart_policy = "OnFailure"

        volume {
          name = "specialists-host"
          host_path {
            path = var.specialists_host_path
            type = "DirectoryOrCreate"
          }
        }
        volume {
          name = "tools-host"
          host_path {
            path = var.tools_host_path
            type = "DirectoryOrCreate"
          }
        }
        volume {
          name = "models-host"
          host_path {
            path = var.models_host_path
            type = "DirectoryOrCreate"
          }
        }
        volume {
          name = "scripts-host"
          host_path {
            path = var.scripts_host_path
            type = "DirectoryOrCreate"
          }
        }
        volume {
          name = "skills-host"
          host_path {
            path = var.skills_host_path
            type = "DirectoryOrCreate"
          }
        }

        volume {
          name = "specialists-pvc"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.if_agent_specialists.metadata[0].name
          }
        }
        volume {
          name = "tools-pvc"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.if_agent_tools.metadata[0].name
          }
        }
        volume {
          name = "models-pvc"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.if_agent_models.metadata[0].name
          }
        }
        volume {
          name = "scripts-pvc"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.if_agent_scripts.metadata[0].name
          }
        }
        volume {
          name = "skills-pvc"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.if_agent_skills.metadata[0].name
          }
        }

        container {
          name  = "sync"
          image = "alpine:3.20"

          command = ["/bin/sh", "-c"]
          args = [
            <<-EOT
              set -eu
              apk add --no-cache rsync
              rsync -a --delete /host/specialists/ /pvc/specialists/
              rsync -a --delete /host/tools/       /pvc/tools/
              rsync -a --delete /host/models/      /pvc/models/
              rsync -a --delete /host/scripts/     /pvc/scripts/
              rsync -a --delete /host/skills/      /pvc/skills/
              echo "config PVC sync complete"
            EOT
          ]

          volume_mount {
            name       = "specialists-host"
            mount_path = "/host/specialists"
            read_only  = true
          }
          volume_mount {
            name       = "tools-host"
            mount_path = "/host/tools"
            read_only  = true
          }
          volume_mount {
            name       = "models-host"
            mount_path = "/host/models"
            read_only  = true
          }
          volume_mount {
            name       = "scripts-host"
            mount_path = "/host/scripts"
            read_only  = true
          }
          volume_mount {
            name       = "skills-host"
            mount_path = "/host/skills"
            read_only  = true
          }

          volume_mount {
            name       = "specialists-pvc"
            mount_path = "/pvc/specialists"
          }
          volume_mount {
            name       = "tools-pvc"
            mount_path = "/pvc/tools"
          }
          volume_mount {
            name       = "models-pvc"
            mount_path = "/pvc/models"
          }
          volume_mount {
            name       = "scripts-pvc"
            mount_path = "/pvc/scripts"
          }
          volume_mount {
            name       = "skills-pvc"
            mount_path = "/pvc/skills"
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_persistent_volume_claim.if_agent_specialists,
    kubernetes_persistent_volume_claim.if_agent_tools,
    kubernetes_persistent_volume_claim.if_agent_models,
    kubernetes_persistent_volume_claim.if_agent_scripts,
    kubernetes_persistent_volume_claim.if_agent_skills,
  ]
}
