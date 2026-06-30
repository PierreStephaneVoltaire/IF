

resource "kubernetes_namespace" "fission" {
  count = var.fission_enabled ? 1 : 0

  metadata {
    name = var.fission_namespace
    labels = {
      app        = "fission"
      managed-by = "terraform"
    }
  }
}
# One-shot Job that syncs the live host directories (specialists, tools,
# models, scripts, skills) into their PVCs on every `terraform apply`. The
# PVCs are the source of truth mounted into the opencode-job (and later the
# agent API) pods; this Job keeps their contents in sync with the repo working
# tree on the node so prompt/specialist/tool/model/skill/script edits are
# reflected without an image rebuild. The `triggers` map is keyed on a sha1
# of the host dirs' file listing so terraform re-runs the Job whenever the
# content changes.
locals {
  config_sync_dirs = [
    { src = var.specialists_host_path, dest = "specialists" },
    { src = var.tools_host_path, dest = "tools" },
    { src = var.models_host_path, dest = "models" },
    { src = var.scripts_host_path, dest = "scripts" },
    { src = var.skills_host_path, dest = "skills" },
  ]
}

# Content-hash trigger: re-runs the sync Job below whenever the file contents
# of any of the five host config directories change.
resource "null_resource" "config_sync_content" {
  count = var.fission_enabled ? 1 : 0

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
  count = var.fission_enabled ? 1 : 0

  metadata {
    name      = "sync-config-pvcs"
    namespace = kubernetes_namespace.if_portals.metadata[0].name
    labels = {
      app        = "config-sync"
      managed-by = "terraform"
    }
    annotations = {
      # Force replacement (re-run) whenever the synced host content changes.
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
            # Install rsync, then mirror each host dir into its PVC. --delete
            # so removed files propagate; the PVC is a mirror, not append-only.
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



resource "null_resource" "fission_crds" {
  count = var.fission_enabled ? 1 : 0

  triggers = {
    fission_version = var.fission_version
  }

  provisioner "local-exec" {
    command = <<-EOT
      kubectl create -k "github.com/fission/fission/crds/v1?ref=v${var.fission_version}" --validate=false || true
    EOT
  }

  depends_on = [kubernetes_namespace.fission]
}

resource "helm_release" "fission" {
  count = var.fission_enabled ? 1 : 0

  name       = "fission"
  namespace  = kubernetes_namespace.fission[0].metadata[0].name
  repository = "https://fission.github.io/fission-charts"
  chart      = "fission-all"
  version    = var.fission_version


  set {
    name  = "serviceType"
    value = "ClusterIP"
  }
  set {
    name  = "routerServiceType"
    value = "ClusterIP"
  }


  set {
    name  = "defaultNamespace"
    value = var.fission_function_namespace
  }


  set {
    name  = "router.roundTrip.timeout"
    value = "${var.fission_router_timeout_seconds * 1000}ms"
  }
  set {
    name  = "router.roundTrip.maxRetries"
    value = "0"
  }


  set {
    name  = "persistence.enabled"
    value = "true"
  }
  set {
    name  = "persistence.storageClassName"
    value = var.storage_class
  }
  set {
    name  = "persistence.size"
    value = "5Gi"
  }


  # Executor — reconciles Function/Environment CRs and rolls the newdeploy
  # function Deployments. During a build wave or mass-respecialize it watches
  # ~100 Functions and creates/scales their Deployments; starve it and
  # specialization stalls → router 504/503. Needs real headroom.
  set {
    name  = "executor.resources.requests.cpu"
    value = "500m"
  }
  set {
    name  = "executor.resources.requests.memory"
    value = "512Mi"
  }
  set {
    name  = "executor.resources.limits.cpu"
    value = "2000m"
  }
  set {
    name  = "executor.resources.limits.memory"
    value = "2Gi"
  }

  # Router — fronts every function call. Low-latency path; under concurrent
  # OpenCode + health tool traffic it holds many in-flight HTTP connections.
  set {
    name  = "router.resources.requests.cpu"
    value = "250m"
  }
  set {
    name  = "router.resources.requests.memory"
    value = "256Mi"
  }
  set {
    name  = "router.resources.limits.cpu"
    value = "1000m"
  }
  set {
    name  = "router.resources.limits.memory"
    value = "1Gi"
  }

  # Buildermgr — the build coordinator. It does NOT run pip itself; it spawns a
  # builder pod PER Package and watches it. But during a full rebuild
  # (reset-fission-packages.sh → ~100 Packages) it's reconciling all of them,
  # archiving source zips, and uploading to storagesvc at once. CPU/memory here
  # bound the control loop, not the builds themselves (those are bounded by
  # the Environment .resources below).
  set {
    name  = "buildermgr.resources.requests.cpu"
    value = "500m"
  }
  set {
    name  = "buildermgr.resources.requests.memory"
    value = "512Mi"
  }
  set {
    name  = "buildermgr.resources.limits.cpu"
    value = "2000m"
  }
  set {
    name  = "buildermgr.resources.limits.memory"
    value = "2Gi"
  }

  # Storagesvc — stores every Package archive and serves them to the fetcher
  # on specialization. pandas/numpy/scipy/chromadb archives are tens of MB;
  # storagesvc buffers them in-memory while streaming. Give it real memory.
  set {
    name  = "storagesvc.resources.requests.cpu"
    value = "250m"
  }
  set {
    name  = "storagesvc.resources.requests.memory"
    value = "512Mi"
  }
  set {
    name  = "storagesvc.resources.limits.cpu"
    value = "1000m"
  }
  set {
    name  = "storagesvc.resources.limits.memory"
    value = "1Gi"
  }

  # Lightweight trigger/controllers — the chart ships them with NO resources
  # (empty {}), which in Kubernetes means UNBOUNDED: the pod can spike to the
  # whole node's allocatable CPU/memory. Bound each so a rogue reconcile loop
  # can't OOMKill the node or starve the heavy components above.
  set {
    name  = "kubewatcher.resources.requests.cpu"
    value = "100m"
  }
  set {
    name  = "kubewatcher.resources.requests.memory"
    value = "128Mi"
  }
  set {
    name  = "kubewatcher.resources.limits.cpu"
    value = "500m"
  }
  set {
    name  = "kubewatcher.resources.limits.memory"
    value = "512Mi"
  }
  set {
    name  = "timer.resources.requests.cpu"
    value = "100m"
  }
  set {
    name  = "timer.resources.requests.memory"
    value = "128Mi"
  }
  set {
    name  = "timer.resources.limits.cpu"
    value = "500m"
  }
  set {
    name  = "timer.resources.limits.memory"
    value = "512Mi"
  }
  set {
    name  = "webhook.resources.requests.cpu"
    value = "100m"
  }
  set {
    name  = "webhook.resources.requests.memory"
    value = "128Mi"
  }
  set {
    name  = "webhook.resources.limits.cpu"
    value = "500m"
  }
  set {
    name  = "webhook.resources.limits.memory"
    value = "512Mi"
  }
  set {
    name  = "mqt_keda.resources.requests.cpu"
    value = "100m"
  }
  set {
    name  = "mqt_keda.resources.requests.memory"
    value = "128Mi"
  }
  set {
    name  = "mqt_keda.resources.limits.cpu"
    value = "500m"
  }
  set {
    name  = "mqt_keda.resources.limits.memory"
    value = "512Mi"
  }

  # Fetcher — the sidecar injected into EVERY function pod. On specialization
  # it downloads the built deploy archive (which for pandas/scipy/chromadb
  # tools is 100-400MB) from storagesvc, unzips it onto a shared emptyDir, then
  # loads it into the runtime container. The chart default is requests
  # cpu=10m mem=16Mi with NO limits — a big fetch OOMs the sidecar mid-load
  # (the classic "no response" / fetcher crash you saw). This is the single
  # biggest cold-start crash source, so it gets the most headroom.
  set {
    name  = "fetcher.resource.cpu.requests"
    value = "200m"
  }
  set {
    name  = "fetcher.resource.cpu.limits"
    value = "2000m"
  }
  set {
    name  = "fetcher.resource.mem.requests"
    value = "256Mi"
  }
  set {
    name  = "fetcher.resource.mem.limits"
    value = "1Gi"
  }

  depends_on = [
    null_resource.fission_crds,
  ]
}



resource "kubectl_manifest" "fission_environment_opencode_runner" {
  count = var.fission_enabled ? 1 : 0

  server_side_apply = true
  force_conflicts   = true

  yaml_body = <<-YAML
    apiVersion: fission.io/v1
    kind: Environment
    metadata:
      name: ${var.fission_environment_name}
      namespace: ${var.fission_function_namespace}
    spec:
      runtime:
        image: ${aws_ecr_repository.if_opencode_runner.repository_url}:latest
      version: 3
      keeparchive: false
      # newdeploy does not pull from the poolmgr pool; poolsize 0 avoids
      # idle pool pods. The function below uses ExecutorType newdeploy.
      poolsize: 0
      imagepullsecret: ecr-registry
      # Bound the builder/runtime pods for this environment. Without this the
      # pods fall back to chart defaults (effectively unbounded) and a heavy
      # opencode-runner image pull / specialization can OOM the node.
      resources:
        requests:
          cpu: 1000m
          memory: 2Gi
        limits:
          cpu: 2000m
          memory: 4Gi
  YAML

  depends_on = [helm_release.fission]
}


resource "kubernetes_service_account" "opencode_runner" {
  count = var.fission_enabled ? 1 : 0

  metadata {
    name      = "opencode-runner"
    namespace = var.fission_function_namespace
    labels = {
      app        = "opencode-runner"
      managed-by = "terraform"
    }
  }
}

resource "kubernetes_secret" "opencode_runner_netrc" {
  count = var.fission_enabled ? 1 : 0

  metadata {
    name      = "opencode-runner-netrc"
    namespace = var.fission_function_namespace
  }

  # .netrc lets the opencode-runner binary authenticate git over HTTPS
  # using the same GitHub PAT that the agent API pod has.
  data = {
    ".netrc" = "machine github.com login x-access-token password ${var.github_token}\n"
  }

  type = "Opaque"
}

resource "kubectl_manifest" "fission_function_opencode_job" {
  count = var.fission_enabled ? 1 : 0

  server_side_apply = true
  force_conflicts   = true

  yaml_body = <<-YAML
    apiVersion: fission.io/v1
    kind: Function
    metadata:
      name: ${var.fission_function_name}
      namespace: ${var.fission_function_namespace}
    spec:
      InvokeStrategy:
        ExecutionStrategy:
          ExecutorType: newdeploy
          # Keep one pod warm so OpenCode jobs never pay the ~42s cold image
          # pull. HPA bursts up to max on concurrent jobs.
          MinScale: 0
          MaxScale: ${var.opencode_runner_max_concurrent}
          SpecializationTimeout: 120
          TargetCPUPercent: 70
        StrategyType: execution
      environment:
        name: ${var.fission_environment_name}
        namespace: ${var.fission_function_namespace}
      package:
        packageref:
          name: ${var.fission_function_name}-pkg
          namespace: ${var.fission_function_namespace}
      podspec:
        terminationGracePeriodSeconds: 360
        imagePullSecrets:
          - name: ${kubernetes_secret.ecr_registry.metadata[0].name}
        containers:
          - name: ${var.fission_function_name}
            image: ${aws_ecr_repository.if_opencode_runner.repository_url}:latest
            imagePullPolicy: IfNotPresent
            command: ["/app/opencode-runner"]
            ports:
              - containerPort: 8888
            readinessProbe:
              httpGet:
                path: /healthz
                port: 8888
              initialDelaySeconds: 3
              periodSeconds: 5
              failureThreshold: 6
            env:
              - name: PORT
                value: "8888"
              - name: HOST
                value: "0.0.0.0"
              - name: OPENCODE_WORKSPACE_BASE
                value: "/app/src/data/conversations"
            envFrom:
              - secretRef:
                  name: ${kubernetes_secret.if_agent_api_secrets.metadata[0].name}
              - configMapRef:
                  name: ${kubernetes_config_map.if_agent_api_config.metadata[0].name}
              - configMapRef:
                  name: ${kubernetes_config_map.if_agent_api_model_config.metadata[0].name}
            resources:
              limits:
                memory: ${var.opencode_runner_memory_mb}Mi
                cpu: ${var.opencode_runner_cpu_millicores}m
              requests:
                memory: ${var.opencode_runner_memory_request_mb}Mi
                cpu: ${var.opencode_runner_cpu_request_millicores}m
            volumeMounts:
              - name: data-storage
                mountPath: /app/src/data
              - name: sandbox-storage
                mountPath: /app/src/sandbox
              - name: conversations-storage
                mountPath: /app/src/data/conversations
              - name: facts-storage
                mountPath: /app/src/data/facts
              - name: aws-credentials
                mountPath: /root/.aws/credentials
                subPath: credentials
                readOnly: true
              - name: aws-credentials
                mountPath: /root/.aws/config
                subPath: config
                readOnly: true
              - name: netrc
                mountPath: /root/.netrc
                subPath: .netrc
                readOnly: true
              # Shared PVCs (same claims the agent API mounts) so prompt /
              # specialist / tool / model / skill / script updates written to
              # the PVC are picked up by the next pod Fission spawns — no image
              # rebuild needed.
              - name: specialists-directory
                mountPath: /app/specialists
                readOnly: true
              - name: tools-directory
                mountPath: /app/tools
                readOnly: true
              - name: models-directory
                mountPath: /app/models
                readOnly: true
              - name: skills-directory
                mountPath: /app/skills
                readOnly: true
              - name: scripts-directory
                mountPath: /app/scripts
                readOnly: true
        volumes:
          - name: data-storage
            persistentVolumeClaim:
              claimName: ${kubernetes_persistent_volume_claim.if_agent_data.metadata[0].name}
          - name: sandbox-storage
            persistentVolumeClaim:
              claimName: ${kubernetes_persistent_volume_claim.if_agent_sandbox.metadata[0].name}
          - name: conversations-storage
            persistentVolumeClaim:
              claimName: ${kubernetes_persistent_volume_claim.if_agent_conversations.metadata[0].name}
          - name: facts-storage
            persistentVolumeClaim:
              claimName: ${kubernetes_persistent_volume_claim.if_agent_facts.metadata[0].name}
          - name: aws-credentials
            secret:
              secretName: ${kubernetes_secret.pl_aws_credentials[0].metadata[0].name}
          - name: netrc
            secret:
              secretName: opencode-runner-netrc
          - name: specialists-directory
            persistentVolumeClaim:
              claimName: ${kubernetes_persistent_volume_claim.if_agent_specialists.metadata[0].name}
          - name: tools-directory
            persistentVolumeClaim:
              claimName: ${kubernetes_persistent_volume_claim.if_agent_tools.metadata[0].name}
          - name: models-directory
            persistentVolumeClaim:
              claimName: ${kubernetes_persistent_volume_claim.if_agent_models.metadata[0].name}
          - name: skills-directory
            persistentVolumeClaim:
              claimName: ${kubernetes_persistent_volume_claim.if_agent_skills.metadata[0].name}
          - name: scripts-directory
            persistentVolumeClaim:
              claimName: ${kubernetes_persistent_volume_claim.if_agent_scripts.metadata[0].name}
  YAML

  depends_on = [
    kubectl_manifest.fission_environment_opencode_runner,
    kubernetes_service_account.opencode_runner,
    kubernetes_secret.opencode_runner_netrc,
    kubernetes_persistent_volume_claim.if_agent_data,
    kubernetes_persistent_volume_claim.if_agent_sandbox,
    kubernetes_persistent_volume_claim.if_agent_conversations,
    kubernetes_persistent_volume_claim.if_agent_facts,
    kubernetes_persistent_volume_claim.if_agent_specialists,
    kubernetes_persistent_volume_claim.if_agent_tools,
    kubernetes_persistent_volume_claim.if_agent_models,
    kubernetes_persistent_volume_claim.if_agent_scripts,
    kubernetes_persistent_volume_claim.if_agent_skills,
    kubernetes_job.sync_config_pvcs[0],
    kubernetes_secret.pl_aws_credentials[0],
    kubernetes_secret.if_agent_api_secrets,
    kubernetes_config_map.if_agent_api_config,
    kubernetes_config_map.if_agent_api_model_config,
    kubernetes_secret.ecr_registry,
    null_resource.packer_build_opencode_runner,
  ]
}


# Stub Package for the opencode-job Function. The Fission *container*
# executor does not fetch or specialize from a deploy archive — it runs the
# Environment image directly with the Function's podspec merged in. The
# Function CRD still requires a `package` ref, so we create a minimal
# Package with an empty literal archive to satisfy validation. Nothing
# ever downloads it; the runner binary lives in the env image.
resource "kubectl_manifest" "fission_package_opencode_job" {
  count = var.fission_enabled ? 1 : 0

  server_side_apply = true
  force_conflicts   = true

  yaml_body = <<-YAML
    apiVersion: fission.io/v1
    kind: Package
    metadata:
      name: ${var.fission_function_name}-pkg
      namespace: ${var.fission_function_namespace}
    spec:
      environment:
        name: ${var.fission_environment_name}
        namespace: ${var.fission_function_namespace}
      deployment:
        # Minimal valid zip (empty archive end-of-central-directory record),
        # base64-encoded. The container executor never reads it.
        literal: "UEsFBgAAAAAAAAAAAAAAAAAAAAAAAA=="
      buildcmd: ""
  YAML

  depends_on = [kubectl_manifest.fission_environment_opencode_runner]
}


resource "kubectl_manifest" "fission_http_trigger_opencode_job" {
  count = var.fission_enabled ? 1 : 0

  yaml_body = <<-YAML
    apiVersion: fission.io/v1
    kind: HTTPTrigger
    metadata:
      name: ${var.fission_function_name}
      namespace: ${var.fission_function_namespace}
    spec:
      functionref:
        type: name
        name: ${var.fission_function_name}
      methods:
        - POST
      relativeurl: ${var.fission_http_trigger_url}
  YAML

  depends_on = [kubectl_manifest.fission_function_opencode_job]
}
