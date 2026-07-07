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
      resources = merge(
        local.pl_default_resources,
        try(yamldecode(file(yaml_path)).resources, {}),
      )
      image_tag  = tool_id
      source_sha = sha1(filebase64("${local.pl_build_dir}/${tool_id}.zip"))
    }
  } : {}

  # Scale values are read from each tool's resources.yaml so cold/warm behavior
  # is owned by the function definition, not by a class lookup table. pod_*
  # defaults to one warm replica because the portal hits them on every page
  # load; everything else defaults to zero. max_replicas / target_cpu /
  # idle_timeout_seconds fall back to the class profile when a tool omits
  # them so the cluster does not get a free-for-all.
  pl_scale_defaults = {
    ai    = { max = 1, cpu = 70, timeout = 120 }
    warm  = { max = 2, cpu = 70, timeout = 60 }
    stats = { max = 2, cpu = 80, timeout = 120 }
    det   = { max = 3, cpu = 70, timeout = 90 }
  }

  pl_tool_scale = var.fission_enabled ? {
    for tool_id, yaml_path in local.pl_tool_yaml_paths :
    tool_id => merge(
      {
        min = startswith(tool_id, "pod_") ? 1 : 0
      },
      local.pl_scale_defaults[local.pl_tools[tool_id].class],
      {
        for k, v in {
          min     = try(yamldecode(file(yaml_path)).min_replicas, null)
          max     = try(yamldecode(file(yaml_path)).max_replicas, null)
          cpu     = try(yamldecode(file(yaml_path)).target_cpu, null)
          timeout = try(yamldecode(file(yaml_path)).idle_timeout_seconds, null)
        } : k => v if v != null
      },
    )
  } : {}

  pl_common_env = [
    { name = "IF_AWS_REGION", value = "ca-central-1" },
    { name = "IF_HEALTH_TABLE_NAME", value = "if-health" },
    { name = "IF_TEMPLATES_TABLE_NAME", value = "if-health-templates" },
    { name = "IF_SESSIONS_TABLE_NAME", value = "if-sessions" },
    { name = "IF_ANALYSIS_CACHE_TABLE_NAME", value = "if-powerlifting-analysis-cache" },
    { name = "POWERLIFTING_MASTER_COMPETITIONS_TABLE", value = "if-powerlifting-master-competitions" },
    { name = "POWERLIFTING_USER_COMPETITIONS_TABLE", value = "if-powerlifting-user-competitions" },
    { name = "HEALTH_PROGRAM_PK", value = "operator" },
    { name = "LLM_BASE_URL", value = "https://openrouter.ai/api/v1" },
  ]

  pl_ai_env = [
    { name = "ANALYSIS_MODEL", value = var.pl_analysis_model },
    { name = "ESTIMATE_MODEL", value = var.pl_estimate_model },
    { name = "IMPORT_FAST_MODEL", value = var.pl_import_fast_model },
    { name = "GLOSSARY_TEXT_MODEL", value = var.pl_glossary_text_model },
  ]
  pl_resources_hash = sha1(join("\n", [for p in values(local.pl_tool_yaml_paths) : sha1(file(p))]))
}

# With the container executor, the ECR image IS the function — no Environment,
# no Package, no fetcher. The images are built and pushed by the powerlifting
# repo's GitHub Actions workflow into the shared ECR repo, tagged "<tool_id>".

resource "kubectl_manifest" "pl_functions" {
  for_each          = local.pl_tools
  server_side_apply = true
  force_conflicts   = true
  yaml_body = yamlencode({
    apiVersion = "fission.io/v1"
    kind       = "Function"
    metadata   = { name = "pl-fn-${local.pl_dns_name[each.key]}", namespace = kubernetes_namespace.if_portals.metadata[0].name }
    spec = {
      environment     = { namespace = kubernetes_namespace.if_portals.metadata[0].name }
      package         = { functionName = "main" }
      functionTimeout = try(each.value.timeout, 900)
      concurrency     = 500
      InvokeStrategy = {
        StrategyType = "execution"
        ExecutionStrategy = {
          ExecutorType          = "container"
          MinScale              = local.pl_tool_scale[each.key].min
          MaxScale              = local.pl_tool_scale[each.key].max
          SpecializationTimeout = local.pl_tool_scale[each.key].timeout
          TargetCPUPercent      = local.pl_tool_scale[each.key].cpu
        }
      }
      podspec = {
        terminationGracePeriodSeconds = 120
        containers = [
          {
            name            = "pl-fn-${local.pl_dns_name[each.key]}"
            image           = "${aws_ecr_repository.pl_fns.repository_url}:${each.value.image_tag}"
            imagePullPolicy = "Always"
            env = concat(
              local.pl_common_env,
              [{ name = "IF_TOOL_NAME", value = each.key }],
              [
                { name = "AWS_SHARED_CREDENTIALS_FILE", value = "/secrets/aws-credentials/credentials" },
                { name = "AWS_CONFIG_FILE", value = "/secrets/aws-credentials/config" },
              ],
              each.value.class == "ai" ? local.pl_ai_env : [],
              each.value.s3_read ? [{ name = "POWERLIFTING_S3_BUCKET", value = var.powerlifting_s3_bucket }] : [],
            )
            envFrom = [
              { secretRef = { name = "pl-fission-secrets" } },
            ]
            ports     = [{ containerPort = 8888 }]
            resources = each.value.resources
            volumeMounts = [
              { name = "aws-creds", mountPath = "/secrets/aws-credentials", readOnly = true },
            ]
          },
        ]
        volumes = [
          { name = "aws-creds", secret = { secretName = "pl-aws-credentials" } },
        ]
        imagePullSecrets = [
          { name = kubernetes_secret.ecr_registry.metadata[0].name },
        ]
      }
    }
  })
  depends_on = [aws_ecr_repository.pl_fns, kubernetes_secret.pl_fission_secrets, kubernetes_secret.pl_aws_credentials]
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
