

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


  set {
    name  = "executor.resources.requests.memory"
    value = "256Mi"
  }
  set {
    name  = "executor.resources.limits.memory"
    value = "512Mi"
  }
  set {
    name  = "router.resources.requests.memory"
    value = "128Mi"
  }
  set {
    name  = "router.resources.limits.memory"
    value = "512Mi"
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
          MinScale: 1
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
        serviceAccountName: opencode-runner
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
            securityContext:
              privileged: true
              runAsUser: 0
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
                mountPath: /root/.aws
                readOnly: true
              - name: netrc
                mountPath: /root/.netrc
                subPath: .netrc
                readOnly: true
              # Runtime-mounted prompt / specialist / tool directories.
              # These point at the live project dirs on the node so prompt
              # and specialist YAML updates are picked up by the next pod
              # Fission spawns — no image rebuild needed.
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
            hostPath:
              path: ${var.aws_credentials_host_path}
              type: Directory
          - name: netrc
            secret:
              secretName: opencode-runner-netrc
          # HostPath mounts for live prompt / specialist / tool dirs.
          - name: specialists-directory
            hostPath:
              path: ${var.specialists_host_path}
              type: DirectoryOrCreate
          - name: tools-directory
            hostPath:
              path: ${var.tools_host_path}
              type: DirectoryOrCreate
          - name: models-directory
            hostPath:
              path: ${var.models_host_path}
              type: DirectoryOrCreate
          - name: skills-directory
            hostPath:
              path: ${var.skills_host_path}
              type: DirectoryOrCreate
          - name: scripts-directory
            hostPath:
              path: ${var.scripts_host_path}
              type: DirectoryOrCreate
  YAML

  depends_on = [
    kubectl_manifest.fission_environment_opencode_runner,
    kubernetes_service_account.opencode_runner,
    kubernetes_secret.opencode_runner_netrc,
    kubernetes_persistent_volume_claim.if_agent_data,
    kubernetes_persistent_volume_claim.if_agent_sandbox,
    kubernetes_persistent_volume_claim.if_agent_conversations,
    kubernetes_persistent_volume_claim.if_agent_facts,
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
