locals {
  pl_lambda_dir = "${path.module}/../utils/powerlifting-app/lambda"

  pl_build_dir = "${path.module}/../utils/powerlifting-app/terraform/fission-build"

  pl_skip_tools = toset(["layers", "pl_authorizer"])

  pl_dns_name = { for t in keys(local.pl_tools) : t => replace(t, "_", "-") }

  pl_tool_yaml_paths = {
    for f in fileset(local.pl_lambda_dir, "*/resources.yaml") :
    dirname(f) => "${local.pl_lambda_dir}/${f}"
    if !contains(local.pl_skip_tools, dirname(f))
  }

  pl_ai_tools = toset(["budget_advisor", "block_program_evaluation", "block_comparison_synthesis", "budget_priority_timeline", "correlation_analysis", "e1rm_backfill", "fatigue_profile_estimate", "glossary_estimate_e1rm", "glossary_estimate_fatigue", "glossary_generate_text", "glossary_resolve_term", "import_classify_file", "import_parse_file", "lift_profile_estimate_stimulus", "lift_profile_rewrite", "lift_profile_review", "muscle_group_estimate", "program_evaluation", "template_evaluate", "multi_block_comparison"])

  pl_warm_reads = toset(["health_get_program", "health_get_session", "health_get_sessions_range", "template_list", "glossary_list_terms", "get_analysis_markdown", "program_list", "session_list", "import_list", "federation_list"])

  pl_stats_tools = toset(["analyze_powerlifting_stats", "powerlifting_filter_categories", "powerlifting_ranking_percentile", "analyze_progression", "analyze_rpe_drift"])

  # Per-function CPU/memory requests AND limits come from each tool's
  # resources.yaml (resources.requests / resources.limits), with sane defaults.
  # The Environment spec.resources only sets the poolmgr fetcher/builder floor;
  # these per-function resources are merged into the Function podspec below so
  # each function pod sizes itself instead of every pod sharing one hard-coded
  # envelope.
  pl_default_resources = {
    requests = { cpu = "100m", memory = "128Mi" }
    limits   = { cpu = "1000m", memory = "512Mi" }
  }

  pl_tools = var.fission_enabled ? {
    for tool_id, yaml_path in local.pl_tool_yaml_paths :
    tool_id => {
      class       = contains(local.pl_ai_tools, tool_id) ? "ai" : contains(local.pl_warm_reads, tool_id) ? "warm" : contains(local.pl_stats_tools, tool_id) ? "stats" : "det"
      is_registry = tool_id == "tool_registry"
      memory      = try(yamldecode(file(yaml_path)).memory, 256)
      timeout     = try(yamldecode(file(yaml_path)).timeout, 900)
      s3_read     = try(yamldecode(file(yaml_path)).s3_read, false)
      # resources block straight from resources.yaml (cpu+memory req+limits),
      # falling back to defaults where the yaml omits a field.
      resources = merge(
        local.pl_default_resources,
        try(yamldecode(file(yaml_path)).resources, {}),
      )
      # Content hash of the built source zip -> unique image tag. A code change
      # produces a new tag, so the Package spec below changes and Fission re-pulls
      # the image. This is the watch-for-code-change mechanism.
      image_tag = "${tool_id}-${substr(sha1(filebase64("${local.pl_build_dir}/${tool_id}.zip")), 0, 12)}"
    }
  } : {}

  pl_scale = {
    ai    = { min = 0, max = 1, cpu = 70, timeout = 120 }
    warm  = { min = 0, max = 2, cpu = 70, timeout = 60 }
    stats = { min = 0, max = 2, cpu = 80, timeout = 120 }
    det   = { min = 0, max = 3, cpu = 70, timeout = 90 }
  }

  pl_common_env = [
    { name = "IF_AWS_REGION", value = "ca-central-1" },
    { name = "IF_HEALTH_TABLE_NAME", value = "if-health" },
    { name = "IF_TEMPLATES_TABLE_NAME", value = "if-health-templates" },
    { name = "IF_SESSIONS_TABLE_NAME", value = "if-sessions" },
    { name = "IF_ANALYSIS_CACHE_TABLE_NAME", value = "if-powerlifting-analysis-cache" },
    { name = "HEALTH_PROGRAM_PK", value = "operator" },
    { name = "LLM_BASE_URL", value = "https://openrouter.ai/api/v1" },
  ]

  pl_ai_env = [
    { name = "ANALYSIS_MODEL", value = "anthropic/claude-sonnet-4.6" },
    { name = "ESTIMATE_MODEL", value = "anthropic/claude-sonnet-4.6" },
    { name = "IMPORT_FAST_MODEL", value = "anthropic/claude-haiku-4.5" },
    { name = "GLOSSARY_TEXT_MODEL", value = "google/gemini-3.1-flash-lite" },
  ]
  pl_resources_hash = sha1(join("\n", [for p in values(local.pl_tool_yaml_paths) : sha1(file(p))]))
}

resource "kubectl_manifest" "pl_fission_env" {
  count             = var.fission_enabled ? 1 : 0
  server_side_apply = true
  force_conflicts   = true
  yaml_body = yamlencode({
    apiVersion = "fission.io/v1"
    kind       = "Environment"
    metadata   = { name = "pl-fission-tools", namespace = kubernetes_namespace.if_portals.metadata[0].name }
    spec = {
      version                = 3
      keeparchive            = false
      runtime                = { image = "ghcr.io/fission/python-env" }
      builder                = { image = "ghcr.io/fission/python-builder" }
      terminationGracePeriod = 120
      resources = {
        requests = { cpu = "500m", memory = "512Mi" }
        limits   = { cpu = "2000m", memory = "2Gi" }
      }
    }
  })
  depends_on = [helm_release.fission]
}

resource "kubectl_manifest" "pl_fission_executor_env_rbac" {
  count             = var.fission_enabled ? 1 : 0
  server_side_apply = true
  force_conflicts   = true
  yaml_body = yamlencode({
    apiVersion = "rbac.authorization.k8s.io/v1"
    kind       = "Role"
    metadata   = { name = "fission-executor-env-reader", namespace = var.fission_namespace }
    rules = [{
      apiGroups = ["fission.io"]
      resources = ["environments", "functions", "packages", "httptriggers", "kuberneteswatchtriggers", "messagequeuetriggers", "timetriggers"]
      verbs     = ["get", "list", "watch"]
    }]
  })
  depends_on = [helm_release.fission]
}

resource "kubectl_manifest" "pl_fission_executor_env_rbac_binding" {
  count             = var.fission_enabled ? 1 : 0
  server_side_apply = true
  force_conflicts   = true
  yaml_body = yamlencode({
    apiVersion = "rbac.authorization.k8s.io/v1"
    kind       = "RoleBinding"
    metadata   = { name = "fission-executor-env-reader", namespace = var.fission_namespace }
    roleRef = {
      apiGroup = "rbac.authorization.k8s.io"
      kind     = "Role"
      name     = "fission-executor-env-reader"
    }
    subjects = [{
      kind      = "ServiceAccount"
      name      = "fission-executor"
      namespace = var.fission_namespace
    }]
  })
  depends_on = [kubectl_manifest.pl_fission_executor_env_rbac]
}

# Powerlifting Fission tool Packages reference a PREBUILT OCI image per tool
# (Package.spec.deployment.oci.image) instead of a source archive + buildcmd.
# This sidesteps the fission buildmgr entirely: no source build, no fetcher
# upload, no HTTP 413 on large scipy archives, no single-builder concurrency
# collisions. The images are built by scripts/build-powerlifting-fn-images.sh
# (and re-built automatically on `terraform apply` via the
# null_resource.packer_build_pl_fn watch loop below) into the shared
# ${prefix}-if-health ECR repo, tagged "<tool_id>-<source_sha>".
#
# NOTE: apply the ECR repo + run the image build BEFORE the first apply of these
# Packages, or set pl_images_prebuilt=true to skip the packer trigger (see var).
resource "kubectl_manifest" "pl_packages" {
  for_each          = local.pl_tools
  server_side_apply = true
  force_conflicts   = true
  yaml_body = yamlencode({
    apiVersion = "fission.io/v1"
    kind       = "Package"
    metadata   = { name = "pl-pkg-${local.pl_dns_name[each.key]}", namespace = kubernetes_namespace.if_portals.metadata[0].name }
    spec = {
      environment = { name = "pl-fission-tools", namespace = kubernetes_namespace.if_portals.metadata[0].name }
      deployment = {
        type = "oci"
        oci = {
          image = "${aws_ecr_repository.if_health_fns.repository_url}:${each.value.image_tag}"
          imagePullSecrets = [
            { name = kubernetes_secret.ecr_registry.metadata[0].name }
          ]
        }
      }
    }
  })
  depends_on = [kubectl_manifest.pl_fission_env, null_resource.packer_build_pl_fn]
}

# ─── Watch loop: rebuild a tool's OCI image when its source zip changes ───
# Mirrors the portal frontend/backend image pattern in image.tf. The trigger is
# the sha1 of the built source zip, so editing a function's code ->
# fission-deploy.py rebuilds the zip -> terraform sees a new hash -> packer
# rebuilds + pushes a new <tool>-<sha> image -> the Package spec.oci.image tag
# changes -> Fission re-pulls and re-specialises the function pod.
resource "null_resource" "packer_build_pl_fn" {
  for_each = local.pl_tools

  triggers = {
    source_sha1 = sha1(filebase64("${local.pl_build_dir}/${each.key}.zip"))
    repo_url    = aws_ecr_repository.if_health_fns.repository_url
    image_tag   = each.value.image_tag
  }

  provisioner "local-exec" {
    working_dir = "${path.module}/../docker"
    command     = <<-EOT
      set -e
      aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws
      aws ecr get-login-password --region ${var.region} | docker login --username AWS --password-stdin $(echo ${aws_ecr_repository.if_health_fns.repository_url} | cut -d'/' -f1)
      packer init powerlifting-fn.pkr.hcl
      packer build \
        -var "image_repository=${aws_ecr_repository.if_health_fns.repository_url}" \
        -var "image_tag=${each.value.image_tag}" \
        -var "tool_id=${each.key}" \
        -var "source_archive=${local.pl_build_dir}/${each.key}.zip" \
        powerlifting-fn.pkr.hcl
    EOT
  }

  depends_on = [aws_ecr_repository.if_health_fns, kubernetes_secret.ecr_registry]
}

resource "kubectl_manifest" "pl_functions" {
  for_each          = local.pl_tools
  server_side_apply = true
  force_conflicts   = true
  yaml_body = yamlencode({
    apiVersion = "fission.io/v1"
    kind       = "Function"
    metadata   = { name = "pl-fn-${local.pl_dns_name[each.key]}", namespace = kubernetes_namespace.if_portals.metadata[0].name }
    spec = {
      environment = { name = "pl-fission-tools", namespace = kubernetes_namespace.if_portals.metadata[0].name }
      package = {
        packageref   = { name = "pl-pkg-${local.pl_dns_name[each.key]}", namespace = kubernetes_namespace.if_portals.metadata[0].name }
        functionName = "main.main"
      }
      functionTimeout = try(each.value.timeout, 900)
      concurrency     = 500
      InvokeStrategy = {
        StrategyType = "execution"
        ExecutionStrategy = {
          ExecutorType          = "newdeploy"
          MinScale              = local.pl_scale[each.value.class].min
          MaxScale              = local.pl_scale[each.value.class].max
          SpecializationTimeout = local.pl_scale[each.value.class].timeout
          TargetCPUPercent      = local.pl_scale[each.value.class].cpu
        }
      }
      # Fission-native secret mounting: the `secrets` field mounts each
      # referenced Secret under /secrets/<namespace>/<secret-name>/<key>.
      # This is the ONLY mechanism Fission v1.26 newdeploy honors — the
      # Function podspec (env, volumes, volumeMounts, envFrom) is NOT merged
      # into the runtime deployment by the newdeploy executor.
      # fission_entry.py discovers /secrets/*/pl-aws-credentials/credentials
      # at import time and sets AWS_SHARED_CREDENTIALS_FILE / AWS_REGION so
      # boto3 finds the creds without any podspec env.
      secrets = [
        { name = "pl-aws-credentials", namespace = kubernetes_namespace.if_portals.metadata[0].name },
        { name = "pl-fission-secrets", namespace = kubernetes_namespace.if_portals.metadata[0].name },
      ]
      podspec = {
        containers = [
          {
            name            = "pl-fission-tools"
            image           = "ghcr.io/fission/python-env"
            imagePullPolicy = "IfNotPresent"
            resources       = each.value.resources
          },
        ]
      }
    }
  })
  depends_on = [kubectl_manifest.pl_packages, kubernetes_secret.pl_fission_secrets, kubernetes_secret.pl_aws_credentials]
}

resource "kubectl_manifest" "pl_triggers" {
  for_each          = local.pl_tools
  server_side_apply = true
  force_conflicts   = true
  yaml_body = yamlencode({
    apiVersion = "fission.io/v1"
    kind       = "HTTPTrigger"
    metadata   = { name = "pl-ht-${local.pl_dns_name[each.key]}", namespace = kubernetes_namespace.if_portals.metadata[0].name }
    spec = {
      functionref = { type = "name", name = "pl-fn-${local.pl_dns_name[each.key]}" }
      # tool_registry serves the OpenAPI discovery doc that health_lambda_mcp
      # fetches (GET /openapi.json) to register the health tools. It must be a
      # public GET — the IF agent API reads it during startup before it has a
      # caller token. Every other tool stays POST. NOTE: Fission v1.26
      # HTTPTrigger has NO authorizer/prefn field in its CRD schema (only
      # functionref/methods/relativeurl/host/prefix/keepPrefix/routeConfig/
      # corsConfig/createingress/ingressconfig). The pl-authorizer is NOT
      # wired here; if per-tool auth is needed later it must live in the
      # tool entrypoint or a Gateway API filter, not the trigger. (fission_repair.md)
      methods     = each.value.is_registry ? ["GET"] : ["POST"]
      relativeurl = each.value.is_registry ? "/openapi.json" : "/${each.key}"
    }
  })
  depends_on = [kubectl_manifest.pl_functions]
}
