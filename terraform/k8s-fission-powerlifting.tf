locals {
  pl_lambda_dir = "${path.module}/../utils/powerlifting-app/lambda"

  pl_build_dir = "${path.module}/../utils/powerlifting-app/terraform/fission-build"

  pl_skip_tools = toset(["layers", "pl_authorizer", "tool_registry"])

  pl_dns_name = { for t in keys(local.pl_tools) : t => replace(t, "_", "-") }

  pl_tool_yaml_paths = {
    for f in fileset(local.pl_lambda_dir, "*/resources.yaml") :
    dirname(f) => "${local.pl_lambda_dir}/${f}"
    if !contains(local.pl_skip_tools, dirname(f))
  }

  pl_ai_tools = toset(["budget_advisor", "block_program_evaluation", "block_comparison_synthesis", "budget_priority_timeline", "correlation_analysis", "e1rm_backfill", "fatigue_profile_estimate", "glossary_estimate_e1rm", "glossary_estimate_fatigue", "glossary_generate_text", "glossary_resolve_term", "import_classify_file", "import_parse_file", "lift_profile_estimate_stimulus", "lift_profile_rewrite", "lift_profile_review", "muscle_group_estimate", "program_evaluation", "template_evaluate", "multi_block_comparison"])

  pl_warm_reads = toset(["health_get_program", "health_get_session", "health_get_sessions_range", "template_list", "glossary_list_terms", "get_analysis_markdown", "program_list", "session_list", "import_list", "federation_list"])

  pl_stats_tools = toset(["analyze_powerlifting_stats", "powerlifting_filter_categories", "powerlifting_ranking_percentile", "analyze_progression", "analyze_rpe_drift"])

  pl_tools = var.fission_enabled ? {
    for tool_id, yaml_path in local.pl_tool_yaml_paths :
    tool_id => {
      class       = contains(local.pl_ai_tools, tool_id) ? "ai" : contains(local.pl_warm_reads, tool_id) ? "warm" : contains(local.pl_stats_tools, tool_id) ? "stats" : "det"
      is_registry = tool_id == "tool_registry"
      memory      = try(yamldecode(file(yaml_path)).memory, 256)
      timeout     = try(yamldecode(file(yaml_path)).timeout, 900)
      s3_read     = try(yamldecode(file(yaml_path)).s3_read, false)
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
        requests = { cpu = "100m", memory = "128Mi" }
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
      deployment  = { type = "literal", literal = filebase64("${local.pl_build_dir}/${each.key}.zip") }
    }
  })
  depends_on = [kubectl_manifest.pl_fission_env]
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
      podspec = {
        serviceAccountName = "default"
        containers = [
          {
            name            = "pl-fission-tools"
            image           = "ghcr.io/fission/python-env"
            imagePullPolicy = "IfNotPresent"
            env = concat(
              local.pl_common_env,
              [{ name = "IF_TOOL_NAME", value = each.key }],
              each.value.class == "ai" ? local.pl_ai_env : [],
              try(each.value.s3_read, false) ? [{ name = "POWERLIFTING_S3_BUCKET", value = var.powerlifting_s3_bucket }] : [],
            )
            envFrom = [{ secretRef = { name = "pl-fission-secrets" } }]
            resources = {
              requests = { cpu = "100m", memory = "${max(128, try(each.value.memory, 256) / 2)}Mi" }
              limits   = { cpu = "1000m", memory = "${try(each.value.memory, 256)}Mi" }
            }
          },
        ]
        volumes = []
      }
    }
  })
  depends_on = [kubectl_manifest.pl_packages, kubernetes_secret.pl_fission_secrets]
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
      methods     = ["POST"]
      relativeurl = "/${each.key}"
    }
  })
  depends_on = [kubectl_manifest.pl_functions]
}
