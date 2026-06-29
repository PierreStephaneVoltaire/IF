resource "kubectl_manifest" "pl_fission_env" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Environment
metadata:
  name: pl-fission-tools
  namespace: fission
spec:
  version: 3
  keeparchive: false
  runtime:
    image: ghcr.io/fission/python-env
  builder:
    image: ghcr.io/fission/python-builder
  terminationGracePeriod: 120
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 1000m
      memory: 512Mi
YAML
}

resource "kubectl_manifest" "pl_pkg_analysis_section" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-analysis_section
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: analysis_section.zip
YAML
}

resource "kubectl_manifest" "pl_fn_analysis_section" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-analysis_section
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-analysis_section
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: analysis_section
    description: "Compute one weekly analysis section only. Use this for asynchronous section caches; it does not build the full weekly analysis report."
    inputSchema: |
      type: object
      properties:
        section:
          type: string
          enum:
          - overview
          - fatigue_readiness
          - peaking
          - workload
          - alerts
          description: The individual analysis section to compute
        weeks:
          type: integer
          description: Number of weeks to analyze
          default: 1
        block:
          type: string
          description: Program block filter
          default: current
        week_start:
          type: integer
          description: Inclusive training week number to start analysis
        week_end:
          type: integer
          description: Inclusive training week number to end analysis
        window_start:
          type: string
          description: Optional date window start (YYYY-MM-DD) for time-series context
        window_end:
          type: string
          description: Optional date window end (YYYY-MM-DD) for time-series context
        ref_date:
          type: string
          description: Optional reference date (YYYY-MM-DD)
        refresh_program:
          type: boolean
          description: Invalidate the program cache before analysis
          default: true
        program:
          type: object
          description: Optional program snapshot supplied by the caller
        sessions:
          type: array
          description: Optional session snapshot supplied by the caller
          items:
            type: object
      required:
      - section
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-analysis_section
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "analysis_section"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_analysis_section" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-analysis_section
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-analysis_section
  methods:
    - POST
  relativeurl: /analysis_section
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_analyze_powerlifting_stats" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-analyze_powerlifting_stats
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: analyze_powerlifting_stats.zip
YAML
}

resource "kubectl_manifest" "pl_fn_analyze_powerlifting_stats" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-analyze_powerlifting_stats
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-analyze_powerlifting_stats
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 2
            SpecializationTimeout: 120
            TargetCPUPercent: 80
  tool:
    name: analyze_powerlifting_stats
    description: "Compares a user's powerlifting stats against the OpenPowerlifting dataset."
    inputSchema: |
      type: object
      properties:
        squat_kg:
          type: number
        bench_kg:
          type: number
        deadlift_kg:
          type: number
        bodyweight_kg:
          type: number
        sex_code:
          type: string
          description: 'User''s sex for DOTS: ''M'' or ''F'''
        federation:
          type: string
        country:
          type: string
        region:
          type: string
        equipment:
          type: string
        sex:
          type: string
        age_class:
          type: string
        year:
          type: integer
        event_type:
          type: string
        min_dots:
          type: number
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-analyze_powerlifting_stats
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: POWERLIFTING_S3_BUCKET
              value: "${var.powerlifting_s3_bucket}"
            - name: IF_TOOL_NAME
              value: "analyze_powerlifting_stats"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_analyze_powerlifting_stats" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-analyze_powerlifting_stats
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-analyze_powerlifting_stats
  methods:
    - POST
  relativeurl: /analyze_powerlifting_stats
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_analyze_progression" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-analyze_progression
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: analyze_progression.zip
YAML
}

resource "kubectl_manifest" "pl_fn_analyze_progression" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-analyze_progression
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-analyze_progression
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 2
            SpecializationTimeout: 120
            TargetCPUPercent: 80
  tool:
    name: analyze_progression
    description: "Calculate weekly progression rate (kg/week) for a lift via Theil-Sen regression on top sets. Returns slope, Kendall tau, fit quality, and data points."
    inputSchema: |
      type: object
      properties:
        exercise_name:
          type: string
          description: Name of the exercise
        weeks:
          type: integer
          description: Number of recent weeks to analyze
      required:
      - exercise_name
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-analyze_progression
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "analyze_progression"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_analyze_progression" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-analyze_progression
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-analyze_progression
  methods:
    - POST
  relativeurl: /analyze_progression
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_analyze_rpe_drift" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-analyze_rpe_drift
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: analyze_rpe_drift.zip
YAML
}

resource "kubectl_manifest" "pl_fn_analyze_rpe_drift" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-analyze_rpe_drift
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-analyze_rpe_drift
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 2
            SpecializationTimeout: 120
            TargetCPUPercent: 80
  tool:
    name: analyze_rpe_drift
    description: "Detect RPE drift for a lift — whether perceived exertion is trending up (fatigue) or down (adaptation)."
    inputSchema: |
      type: object
      properties:
        exercise_name:
          type: string
          description: Name of the exercise
        window_weeks:
          type: integer
          description: Number of weeks to analyze
          default: 4
      required:
      - exercise_name
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-analyze_rpe_drift
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "analyze_rpe_drift"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_analyze_rpe_drift" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-analyze_rpe_drift
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-analyze_rpe_drift
  methods:
    - POST
  relativeurl: /analyze_rpe_drift
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_block_correlation_analysis" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-block_correlation_analysis
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: block_correlation_analysis.zip
YAML
}

resource "kubectl_manifest" "pl_fn_block_correlation_analysis" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-block_correlation_analysis
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-block_correlation_analysis
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: block_correlation_analysis
    description: "AI-powered exercise ROI correlation analysis for a supplied block snapshot. Use this for past blocks so the correlation uses that block's sessions rather than today's rolling window."
    inputSchema: |
      type: object
      properties:
        weeks:
          type: integer
          description: Block length in weeks
          default: 4
        window_start:
          type: string
          description: Block start date (YYYY-MM-DD)
        program:
          type: object
          description: Block-scoped program snapshot
        sessions:
          type: array
          description: Block sessions
          items:
            type: object
      required:
      - program
      - sessions
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-block_correlation_analysis
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "block_correlation_analysis"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_block_correlation_analysis" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-block_correlation_analysis
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-block_correlation_analysis
  methods:
    - POST
  relativeurl: /block_correlation_analysis
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_block_program_evaluation" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-block_program_evaluation
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: block_program_evaluation.zip
YAML
}

resource "kubectl_manifest" "pl_fn_block_program_evaluation" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-block_program_evaluation
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-block_program_evaluation
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 1
            SpecializationTimeout: 120
            TargetCPUPercent: 70
  tool:
    name: block_program_evaluation
    description: "AI program evaluation for a supplied historical block snapshot. The caller supplies a normalized program where the target block sessions are scoped to current. Use this for past-block program analysis without loading the live current program."
    inputSchema: |
      type: object
      properties:
        program:
          type: object
          description: Block-scoped program snapshot to evaluate.
      required:
      - program
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-block_program_evaluation
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: ANALYSIS_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: ESTIMATE_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: IMPORT_FAST_MODEL
              value: "anthropic/claude-haiku-4.5"
            - name: GLOSSARY_TEXT_MODEL
              value: "google/gemini-3.1-flash-lite"
            - name: IF_TOOL_NAME
              value: "block_program_evaluation"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_block_program_evaluation" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-block_program_evaluation
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-block_program_evaluation
  methods:
    - POST
  relativeurl: /block_program_evaluation
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_budget_advisor" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-budget_advisor
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: budget_advisor.zip
YAML
}

resource "kubectl_manifest" "pl_fn_budget_advisor" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-budget_advisor
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-budget_advisor
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 1
            SpecializationTimeout: 120
            TargetCPUPercent: 70
  tool:
    name: budget_advisor
    description: "AI budget triage and pre-competition priority analysis for a powerlifter. Returns a structured assessment: overall status vs monthly cap, locked-in MANDATORY items, suggested cuts when over budget, missing-expense gaps based on the nearest competition, and a coach-facing note. Competition day is the north star — mandatory comp-linked items are never suggested for cuts."
    inputSchema: |
      type: object
      properties:
        config:
          type: object
          description: 'Budget config: monthly_cap (hard cap), currency.'
          properties:
            monthly_cap:
              type: number
            currency:
              type: string
        items:
          type: array
          description: Budget items with id, name, category, cost, recurrence, priority_tier,
            purchased, comp linkage.
          items:
            type: object
        competitions:
          type: array
          description: Optional upcoming competitions with name, start_date, user_status.
          items:
            type: object
        spent_this_month:
          type: number
          description: Total spent in the current month, for over/under-cap reasoning.
      required:
      - config
      - items
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-budget_advisor
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: ANALYSIS_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: ESTIMATE_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: IMPORT_FAST_MODEL
              value: "anthropic/claude-haiku-4.5"
            - name: GLOSSARY_TEXT_MODEL
              value: "google/gemini-3.1-flash-lite"
            - name: IF_TOOL_NAME
              value: "budget_advisor"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_budget_advisor" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-budget_advisor
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-budget_advisor
  methods:
    - POST
  relativeurl: /budget_advisor
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_budget_priority_timeline" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-budget_priority_timeline
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: budget_priority_timeline.zip
YAML
}

resource "kubectl_manifest" "pl_fn_budget_priority_timeline" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-budget_priority_timeline
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-budget_priority_timeline
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 1
            SpecializationTimeout: 120
            TargetCPUPercent: 70
  tool:
    name: budget_priority_timeline
    description: "AI purchase priority timeline for a powerlifting budget. Schedules equipment, supplements, gym/federation memberships, and competition-entry fees across months so the total stays under the monthly cap while ensuring mandatory items are bought before each confirmed/optional competition."
    inputSchema: |
      type: object
      properties:
        config:
          type: object
          description: 'Budget config: monthly_budget, currency, budget_start_month.'
          properties:
            monthly_budget:
              type: number
            currency:
              type: string
            budget_start_month:
              type: string
        items:
          type: array
          description: Budget items (equipment, supplements, memberships, competition entries).
          items:
            type: object
        competitions:
          type: array
          description: Optional upcoming competitions with master_id, name, start_date,
            user_status.
          items:
            type: object
        federation_memberships:
          type: array
          description: 'Optional federation membership state: abbreviation, membership_group,
            membership_paid, membership_cost.'
          items:
            type: object
      required:
      - config
      - items
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-budget_priority_timeline
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: ANALYSIS_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: ESTIMATE_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: IMPORT_FAST_MODEL
              value: "anthropic/claude-haiku-4.5"
            - name: GLOSSARY_TEXT_MODEL
              value: "google/gemini-3.1-flash-lite"
            - name: IF_TOOL_NAME
              value: "budget_priority_timeline"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_budget_priority_timeline" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-budget_priority_timeline
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-budget_priority_timeline
  methods:
    - POST
  relativeurl: /budget_priority_timeline
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_calculate_attempts" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-calculate_attempts
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: calculate_attempts.zip
YAML
}

resource "kubectl_manifest" "pl_fn_calculate_attempts" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-calculate_attempts
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-calculate_attempts
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: calculate_attempts
    description: "Calculate competition attempt weights based on opener."
    inputSchema: |
      type: object
      properties:
        lift:
          type: string
          description: 'Lift type: squat, bench, or deadlift'
        opener_kg:
          type: number
          description: First attempt weight in kg
        j1_override:
          type: number
          description: Override jump 1 from program prefs (kg)
        j2_override:
          type: number
          description: Override jump 2 from program prefs (kg)
        last_felt:
          type: string
          description: If 'hard', halve j2 for conservative third attempt
      required:
      - lift
      - opener_kg
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-calculate_attempts
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "calculate_attempts"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_calculate_attempts" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-calculate_attempts
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-calculate_attempts
  methods:
    - POST
  relativeurl: /calculate_attempts
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_calculate_dots" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-calculate_dots
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: calculate_dots.zip
YAML
}

resource "kubectl_manifest" "pl_fn_calculate_dots" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-calculate_dots
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-calculate_dots
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: calculate_dots
    description: "Calculate DOTS score from competition total and bodyweight."
    inputSchema: |
      type: object
      properties:
        total_kg:
          type: number
          description: Combined squat + bench + deadlift total
        bodyweight_kg:
          type: number
          description: Lifter bodyweight in kg
        sex:
          type: string
          description: '''male'' or ''female'''
      required:
      - total_kg
      - bodyweight_kg
      - sex
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-calculate_dots
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "calculate_dots"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 128Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_calculate_dots" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-calculate_dots
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-calculate_dots
  methods:
    - POST
  relativeurl: /calculate_dots
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_correlation_analysis" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-correlation_analysis
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: correlation_analysis.zip
YAML
}

resource "kubectl_manifest" "pl_fn_correlation_analysis" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-correlation_analysis
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-correlation_analysis
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 1
            SpecializationTimeout: 120
            TargetCPUPercent: 70
  tool:
    name: correlation_analysis
    description: "AI-powered exercise ROI correlation analysis. Identifies which accessory exercises correlate with improvements in squat/bench/deadlift over a rolling window. Results are cached in DynamoDB. Use refresh=true to force regeneration."
    inputSchema: |
      type: object
      properties:
        weeks:
          type: integer
          description: Rolling window in weeks
          default: 4
        block:
          type: string
          description: Program block filter
          default: current
        refresh:
          type: boolean
          description: Force regeneration, ignore cache
          default: false
        cache_only:
          type: boolean
          description: Return only cached results without generating AI output
          default: false
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-correlation_analysis
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: ANALYSIS_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: ESTIMATE_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: IMPORT_FAST_MODEL
              value: "anthropic/claude-haiku-4.5"
            - name: GLOSSARY_TEXT_MODEL
              value: "google/gemini-3.1-flash-lite"
            - name: IF_TOOL_NAME
              value: "correlation_analysis"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_correlation_analysis" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-correlation_analysis
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-correlation_analysis
  methods:
    - POST
  relativeurl: /correlation_analysis
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_days_until" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-days_until
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: days_until.zip
YAML
}

resource "kubectl_manifest" "pl_fn_days_until" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-days_until
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-days_until
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: days_until
    description: "Calculate days until a target date."
    inputSchema: |
      type: object
      properties:
        target_date:
          type: string
          description: Target date (YYYY-MM-DD)
        label:
          type: string
          description: Human label for the milestone
          default: target
      required:
      - target_date
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-days_until
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "days_until"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 128Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_days_until" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-days_until
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-days_until
  methods:
    - POST
  relativeurl: /days_until
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_estimate_1rm" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-estimate_1rm
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: estimate_1rm.zip
YAML
}

resource "kubectl_manifest" "pl_fn_estimate_1rm" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-estimate_1rm
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-estimate_1rm
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: estimate_1rm
    description: "Estimate one-rep max using Epley, Brzycki, and RPE-based formulas."
    inputSchema: |
      type: object
      properties:
        weight_kg:
          type: number
          description: Weight lifted in kg
        reps:
          type: integer
          description: Number of repetitions
        rpe:
          type: integer
          description: RPE of the set (6-10)
      required:
      - weight_kg
      - reps
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-estimate_1rm
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "estimate_1rm"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 128Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_estimate_1rm" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-estimate_1rm
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-estimate_1rm
  methods:
    - POST
  relativeurl: /estimate_1rm
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_export_program_history" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-export_program_history
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: export_program_history.zip
YAML
}

resource "kubectl_manifest" "pl_fn_export_program_history" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-export_program_history
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-export_program_history
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: export_program_history
    description: "Export the full training program to an Excel (.xlsx) or Markdown (.md) file. Sheets: Meta, Current Maxes, Phases, Sessions, Exercises, Competitions, Lift Profiles, Weekly Analysis, Per-Lift Metrics, ROI Correlation, Program Evaluation. The three AI-driven sheets use cached values; refresh on the Analysis page first if needed. After calling, emit a FILES: line to deliver the file."
    inputSchema: |
      type: object
      properties:
        format:
          type: string
          description: 'Export format: ''xlsx'' or ''markdown'''
          default: xlsx
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-export_program_history
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "export_program_history"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_export_program_history" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-export_program_history
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-export_program_history
  methods:
    - POST
  relativeurl: /export_program_history
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_export_program_markdown" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-export_program_markdown
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: export_program_markdown.zip
YAML
}

resource "kubectl_manifest" "pl_fn_export_program_markdown" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-export_program_markdown
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-export_program_markdown
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: export_program_markdown
    description: "Generate the markdown export of the current program and return its content as a string. Used internally by regenerate_analysis."
    inputSchema: |
      type: object
      properties: {}
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-export_program_markdown
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "export_program_markdown"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_export_program_markdown" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-export_program_markdown
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-export_program_markdown
  methods:
    - POST
  relativeurl: /export_program_markdown
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_fatigue_profile_estimate" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-fatigue_profile_estimate
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: fatigue_profile_estimate.zip
YAML
}

resource "kubectl_manifest" "pl_fn_fatigue_profile_estimate" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-fatigue_profile_estimate
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-fatigue_profile_estimate
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 1
            SpecializationTimeout: 120
            TargetCPUPercent: 70
  tool:
    name: fatigue_profile_estimate
    description: "Estimate the fatigue profile (axial/neural/peripheral/systemic components) for an exercise using AI analysis of biomechanical characteristics."
    inputSchema: |
      type: object
      properties:
        exercise:
          type: object
          description: Exercise metadata dict
          properties:
            name:
              type: string
            category:
              type: string
            equipment:
              type: string
            primary_muscles:
              type: array
              items:
                type: string
            secondary_muscles:
              type: array
              items:
                type: string
            tertiary_muscles:
              type: array
              items:
                type: string
            description:
              type: string
            how_to_perform:
              type: string
            why_do_it:
              type: string
      required:
      - exercise
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-fatigue_profile_estimate
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: ANALYSIS_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: ESTIMATE_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: IMPORT_FAST_MODEL
              value: "anthropic/claude-haiku-4.5"
            - name: GLOSSARY_TEXT_MODEL
              value: "google/gemini-3.1-flash-lite"
            - name: IF_TOOL_NAME
              value: "fatigue_profile_estimate"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_fatigue_profile_estimate" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-fatigue_profile_estimate
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-fatigue_profile_estimate
  methods:
    - POST
  relativeurl: /fatigue_profile_estimate
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_get_analysis_markdown" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-get_analysis_markdown
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: get_analysis_markdown.zip
YAML
}

resource "kubectl_manifest" "pl_fn_get_analysis_markdown" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-get_analysis_markdown
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-get_analysis_markdown
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 1
            MaxScale: 2
            SpecializationTimeout: 60
            TargetCPUPercent: 70
  tool:
    name: get_analysis_markdown
    description: "Return the cached markdown export of the full training program (current block). This is the primary reference document for coaching decisions. Use the cache unless it is stale, dirty, or refresh is true."
    inputSchema: |
      type: object
      properties:
        refresh:
          type: boolean
          description: Force regeneration before returning markdown
          default: false
        max_age_hours:
          type: integer
          description: Maximum cache age before regeneration
          default: 72
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-get_analysis_markdown
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "get_analysis_markdown"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_get_analysis_markdown" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-get_analysis_markdown
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-get_analysis_markdown
  methods:
    - POST
  relativeurl: /get_analysis_markdown
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_glossary_add" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-glossary_add
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: glossary_add.zip
YAML
}

resource "kubectl_manifest" "pl_fn_glossary_add" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-glossary_add
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-glossary_add
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: glossary_add
    description: "Add new exercise to glossary."
    inputSchema: |
      type: object
      properties:
        exercise:
          type: object
      required:
      - exercise
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-glossary_add
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "glossary_add"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_glossary_add" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-glossary_add
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-glossary_add
  methods:
    - POST
  relativeurl: /glossary_add
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_glossary_estimate_e1rm" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-glossary_estimate_e1rm
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: glossary_estimate_e1rm.zip
YAML
}

resource "kubectl_manifest" "pl_fn_glossary_estimate_e1rm" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-glossary_estimate_e1rm
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-glossary_estimate_e1rm
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 1
            SpecializationTimeout: 120
            TargetCPUPercent: 70
  tool:
    name: glossary_estimate_e1rm
    description: "AI backfill e1RM estimate for one exercise."
    inputSchema: |
      type: object
      properties:
        id:
          type: string
      required:
      - id
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-glossary_estimate_e1rm
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: ANALYSIS_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: ESTIMATE_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: IMPORT_FAST_MODEL
              value: "anthropic/claude-haiku-4.5"
            - name: GLOSSARY_TEXT_MODEL
              value: "google/gemini-3.1-flash-lite"
            - name: IF_TOOL_NAME
              value: "glossary_estimate_e1rm"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_glossary_estimate_e1rm" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-glossary_estimate_e1rm
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-glossary_estimate_e1rm
  methods:
    - POST
  relativeurl: /glossary_estimate_e1rm
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_glossary_estimate_fatigue" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-glossary_estimate_fatigue
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: glossary_estimate_fatigue.zip
YAML
}

resource "kubectl_manifest" "pl_fn_glossary_estimate_fatigue" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-glossary_estimate_fatigue
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-glossary_estimate_fatigue
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 1
            SpecializationTimeout: 120
            TargetCPUPercent: 70
  tool:
    name: glossary_estimate_fatigue
    description: "AI fatigue profile estimation for one exercise."
    inputSchema: |
      type: object
      properties:
        id:
          type: string
      required:
      - id
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-glossary_estimate_fatigue
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: ANALYSIS_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: ESTIMATE_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: IMPORT_FAST_MODEL
              value: "anthropic/claude-haiku-4.5"
            - name: GLOSSARY_TEXT_MODEL
              value: "google/gemini-3.1-flash-lite"
            - name: IF_TOOL_NAME
              value: "glossary_estimate_fatigue"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_glossary_estimate_fatigue" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-glossary_estimate_fatigue
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-glossary_estimate_fatigue
  methods:
    - POST
  relativeurl: /glossary_estimate_fatigue
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_glossary_estimate_muscles" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-glossary_estimate_muscles
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: glossary_estimate_muscles.zip
YAML
}

resource "kubectl_manifest" "pl_fn_glossary_estimate_muscles" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-glossary_estimate_muscles
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-glossary_estimate_muscles
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: glossary_estimate_muscles
    description: "AI muscle group estimation for one glossary exercise."
    inputSchema: |
      type: object
      properties:
        id:
          type: string
      required:
      - id
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-glossary_estimate_muscles
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "glossary_estimate_muscles"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_glossary_estimate_muscles" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-glossary_estimate_muscles
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-glossary_estimate_muscles
  methods:
    - POST
  relativeurl: /glossary_estimate_muscles
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_glossary_generate_text" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-glossary_generate_text
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: glossary_generate_text.zip
YAML
}

resource "kubectl_manifest" "pl_fn_glossary_generate_text" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-glossary_generate_text
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-glossary_generate_text
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 1
            SpecializationTimeout: 120
            TargetCPUPercent: 70
  tool:
    name: glossary_generate_text
    description: "Generate concise editable glossary text for what an exercise is, how to perform it, and why to use it."
    inputSchema: |
      type: object
      properties:
        exercise:
          type: object
          description: Exercise metadata dict
          properties:
            name:
              type: string
            category:
              type: string
            equipment:
              type: string
            primary_muscles:
              type: array
              items:
                type: string
            secondary_muscles:
              type: array
              items:
                type: string
            tertiary_muscles:
              type: array
              items:
                type: string
            description:
              type: string
            how_to_perform:
              type: string
            why_do_it:
              type: string
        lift_profiles:
          type: array
          items:
            type: object
          description: Optional squat/bench/deadlift lift profiles
      required:
      - exercise
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-glossary_generate_text
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: ANALYSIS_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: ESTIMATE_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: IMPORT_FAST_MODEL
              value: "anthropic/claude-haiku-4.5"
            - name: GLOSSARY_TEXT_MODEL
              value: "google/gemini-3.1-flash-lite"
            - name: IF_TOOL_NAME
              value: "glossary_generate_text"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_glossary_generate_text" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-glossary_generate_text
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-glossary_generate_text
  methods:
    - POST
  relativeurl: /glossary_generate_text
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_glossary_set_e1rm" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-glossary_set_e1rm
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: glossary_set_e1rm.zip
YAML
}

resource "kubectl_manifest" "pl_fn_glossary_set_e1rm" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-glossary_set_e1rm
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-glossary_set_e1rm
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: glossary_set_e1rm
    description: "Manually set e1RM for glossary exercise."
    inputSchema: |
      type: object
      properties:
        id:
          type: string
        value_kg:
          type: number
        method:
          type: string
      required:
      - id
      - value_kg
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-glossary_set_e1rm
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "glossary_set_e1rm"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_glossary_set_e1rm" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-glossary_set_e1rm
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-glossary_set_e1rm
  methods:
    - POST
  relativeurl: /glossary_set_e1rm
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_glossary_update" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-glossary_update
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: glossary_update.zip
YAML
}

resource "kubectl_manifest" "pl_fn_glossary_update" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-glossary_update
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-glossary_update
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: glossary_update
    description: "Update exercise in glossary."
    inputSchema: |
      type: object
      properties:
        id:
          type: string
        fields:
          type: object
      required:
      - id
      - fields
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-glossary_update
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "glossary_update"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_glossary_update" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-glossary_update
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-glossary_update
  methods:
    - POST
  relativeurl: /glossary_update
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_add_exercise" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_add_exercise
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_add_exercise.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_add_exercise" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_add_exercise
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_add_exercise
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_add_exercise
    description: "Add an exercise to a training session."
    inputSchema: |
      type: object
      properties:
        date:
          type: string
          description: Session date (YYYY-MM-DD)
        exercise:
          type: object
          description: 'Exercise dict: {name, sets, reps, kg, rpe, notes}'
      required:
      - date
      - exercise
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_add_exercise
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_add_exercise"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_add_exercise" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_add_exercise
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_add_exercise
  methods:
    - POST
  relativeurl: /health_add_exercise
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_complete_competition" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_complete_competition
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_complete_competition.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_complete_competition" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_complete_competition
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_complete_competition
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_complete_competition
    description: "Mark a competition as completed and compute PRR from the stored snapshot."
    inputSchema: |
      type: object
      properties:
        date:
          type: string
          description: Competition date to complete (YYYY-MM-DD)
        results:
          type: object
          description: Best successful lift attempts and total
        body_weight_kg:
          type: number
          description: Official weigh-in bodyweight in kg
        post_meet_report:
          type: object
          description: Optional structured post-meet attempt and context report
        version:
          type: string
          description: Program version to update
          default: current
        allow_retrospective:
          type: boolean
          description: Allow backfilling a missing T-1 snapshot
          default: true
      required:
      - date
      - results
      - body_weight_kg
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_complete_competition
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_complete_competition"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_complete_competition" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_complete_competition
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_complete_competition
  methods:
    - POST
  relativeurl: /health_complete_competition
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_create_competition" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_create_competition
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_create_competition.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_create_competition" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_create_competition
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_create_competition
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_create_competition
    description: "Create a new competition entry."
    inputSchema: |
      type: object
      properties:
        competition:
          type: object
          description: 'Competition dict: name, date, federation, federation_id, counts_toward_federation_ids,
            status, weight_class_kg, location, targets, notes'
      required:
      - competition
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_create_competition
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_create_competition"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_create_competition" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_create_competition
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_create_competition
  methods:
    - POST
  relativeurl: /health_create_competition
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_create_session" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_create_session
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_create_session.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_create_session" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_create_session
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_create_session
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_create_session
    description: "Create a new training session."
    inputSchema: |
      type: object
      properties:
        date:
          type: string
          description: Session date (YYYY-MM-DD)
        day:
          type: string
          description: Day label e.g. Monday
        week_number:
          type: integer
          description: Training week number
        exercises:
          type: array
          items:
            type: object
          description: Optional list of exercises
        session_notes:
          type: string
          description: Optional session notes
          default: ''
      required:
      - date
      - day
      - week_number
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_create_session
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_create_session"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_create_session" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_create_session
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_create_session
  methods:
    - POST
  relativeurl: /health_create_session
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_delete_competition" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_delete_competition
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_delete_competition.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_delete_competition" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_delete_competition
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_delete_competition
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_delete_competition
    description: "Delete a competition entry by date."
    inputSchema: |
      type: object
      properties:
        date:
          type: string
          description: Competition date to delete (YYYY-MM-DD)
      required:
      - date
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_delete_competition
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_delete_competition"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_delete_competition" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_delete_competition
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_delete_competition
  methods:
    - POST
  relativeurl: /health_delete_competition
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_delete_diet_note" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_delete_diet_note
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_delete_diet_note.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_delete_diet_note" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_delete_diet_note
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_delete_diet_note
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_delete_diet_note
    description: "Delete a diet note by date."
    inputSchema: |
      type: object
      properties:
        date:
          type: string
          description: Diet note date to delete (YYYY-MM-DD)
      required:
      - date
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_delete_diet_note
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_delete_diet_note"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_delete_diet_note" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_delete_diet_note
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_delete_diet_note
  methods:
    - POST
  relativeurl: /health_delete_diet_note
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_delete_session" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_delete_session
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_delete_session.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_delete_session" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_delete_session
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_delete_session
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_delete_session
    description: "Delete a training session by date."
    inputSchema: |
      type: object
      properties:
        date:
          type: string
          description: Session date to delete (YYYY-MM-DD)
      required:
      - date
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_delete_session
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_delete_session"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_delete_session" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_delete_session
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_delete_session
  methods:
    - POST
  relativeurl: /health_delete_session
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_get_competition" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_get_competition
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_get_competition.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_get_competition" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_get_competition
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_get_competition
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_get_competition
    description: "Get competition details by date."
    inputSchema: |
      type: object
      properties:
        date:
          type: string
          description: Competition date (YYYY-MM-DD)
      required:
      - date
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_get_competition
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_get_competition"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_get_competition" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_get_competition
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_get_competition
  methods:
    - POST
  relativeurl: /health_get_competition
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_get_current_maxes" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_get_current_maxes
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_get_current_maxes.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_get_current_maxes" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_get_current_maxes
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_get_current_maxes
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 1
            MaxScale: 2
            SpecializationTimeout: 60
            TargetCPUPercent: 70
  tool:
    name: health_get_current_maxes
    description: "Get current training maxes (squat, bench, deadlift)."
    inputSchema: |
      type: object
      properties: {}
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_get_current_maxes
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_get_current_maxes"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_get_current_maxes" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_get_current_maxes
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_get_current_maxes
  methods:
    - POST
  relativeurl: /health_get_current_maxes
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_get_diet_notes" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_get_diet_notes
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_get_diet_notes.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_get_diet_notes" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_get_diet_notes
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_get_diet_notes
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_get_diet_notes
    description: "Get diet notes for a date range."
    inputSchema: |
      type: object
      properties:
        start_date:
          type: string
          description: Start of date range (YYYY-MM-DD)
        end_date:
          type: string
          description: End of date range (YYYY-MM-DD)
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_get_diet_notes
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_get_diet_notes"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_get_diet_notes" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_get_diet_notes
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_get_diet_notes
  methods:
    - POST
  relativeurl: /health_get_diet_notes
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_get_federation_library" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_get_federation_library
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_get_federation_library.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_get_federation_library" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_get_federation_library
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_get_federation_library
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_get_federation_library
    description: "Get the shared federation and qualification-standards library."
    inputSchema: |
      type: object
      properties: {}
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_get_federation_library
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_get_federation_library"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_get_federation_library" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_get_federation_library
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_get_federation_library
  methods:
    - POST
  relativeurl: /health_get_federation_library
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_get_goals" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_get_goals
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_get_goals.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_get_goals" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_get_goals
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_get_goals
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 1
            MaxScale: 2
            SpecializationTimeout: 60
            TargetCPUPercent: 70
  tool:
    name: health_get_goals
    description: "Get the explicit goals for the current training block."
    inputSchema: |
      type: object
      properties: {}
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_get_goals
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_get_goals"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_get_goals" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_get_goals
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_get_goals
  methods:
    - POST
  relativeurl: /health_get_goals
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_get_meta" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_get_meta
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_get_meta.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_get_meta" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_get_meta
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_get_meta
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 1
            MaxScale: 2
            SpecializationTimeout: 60
            TargetCPUPercent: 70
  tool:
    name: health_get_meta
    description: "Get program metadata (name, dates, weight class, etc.)."
    inputSchema: |
      type: object
      properties: {}
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_get_meta
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_get_meta"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_get_meta" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_get_meta
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_get_meta
  methods:
    - POST
  relativeurl: /health_get_meta
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_get_phases" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_get_phases
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_get_phases.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_get_phases" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_get_phases
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_get_phases
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 1
            MaxScale: 2
            SpecializationTimeout: 60
            TargetCPUPercent: 70
  tool:
    name: health_get_phases
    description: "Get the training phases from the program."
    inputSchema: |
      type: object
      properties: {}
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_get_phases
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_get_phases"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_get_phases" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_get_phases
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_get_phases
  methods:
    - POST
  relativeurl: /health_get_phases
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_get_program" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_get_program
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_get_program.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_get_program" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_get_program
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_get_program
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 1
            MaxScale: 2
            SpecializationTimeout: 60
            TargetCPUPercent: 70
  tool:
    name: health_get_program
    description: "Get the full training program from DynamoDB. Returns the cached program dict with all sessions, phases, meta, and preferences."
    inputSchema: |
      type: object
      properties: {}
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_get_program
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_get_program"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_get_program" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_get_program
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_get_program
  methods:
    - POST
  relativeurl: /health_get_program
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_get_session" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_get_session
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_get_session.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_get_session" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_get_session
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_get_session
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 1
            MaxScale: 2
            SpecializationTimeout: 60
            TargetCPUPercent: 70
  tool:
    name: health_get_session
    description: "Get a single training session by date."
    inputSchema: |
      type: object
      properties:
        date:
          type: string
          description: Session date (YYYY-MM-DD)
      required:
      - date
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_get_session
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_get_session"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_get_session" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_get_session
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_get_session
  methods:
    - POST
  relativeurl: /health_get_session
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_get_sessions_range" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_get_sessions_range
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_get_sessions_range.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_get_sessions_range" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_get_sessions_range
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_get_sessions_range
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 1
            MaxScale: 2
            SpecializationTimeout: 60
            TargetCPUPercent: 70
  tool:
    name: health_get_sessions_range
    description: "Get training sessions for a date range."
    inputSchema: |
      type: object
      properties:
        start_date:
          type: string
          description: Start of date range (YYYY-MM-DD)
        end_date:
          type: string
          description: End of date range (YYYY-MM-DD)
      required:
      - start_date
      - end_date
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_get_sessions_range
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_get_sessions_range"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_get_sessions_range" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_get_sessions_range
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_get_sessions_range
  methods:
    - POST
  relativeurl: /health_get_sessions_range
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_get_supplements" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_get_supplements
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_get_supplements.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_get_supplements" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_get_supplements
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_get_supplements
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_get_supplements
    description: "Get the supplement protocol from the program."
    inputSchema: |
      type: object
      properties: {}
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_get_supplements
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_get_supplements"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_get_supplements" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_get_supplements
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_get_supplements
  methods:
    - POST
  relativeurl: /health_get_supplements
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_invalidate_program_cache" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_invalidate_program_cache
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_invalidate_program_cache.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_invalidate_program_cache" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_invalidate_program_cache
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_invalidate_program_cache
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_invalidate_program_cache
    description: "Clear the in-memory cached training program so the next read loads from DynamoDB."
    inputSchema: |
      type: object
      properties: {}
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_invalidate_program_cache
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_invalidate_program_cache"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_invalidate_program_cache" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_invalidate_program_cache
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_invalidate_program_cache
  methods:
    - POST
  relativeurl: /health_invalidate_program_cache
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_new_version" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_new_version
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_new_version.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_new_version" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_new_version
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_new_version
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_new_version
    description: "Create a new program version with the given patches."
    inputSchema: |
      type: object
      properties:
        change_reason:
          type: string
          description: Human-readable reason for the version change
        patches:
          type: array
          items:
            type: object
          description: List of patches, each with 'path' and 'value' keys
      required:
      - change_reason
      - patches
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_new_version
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_new_version"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_new_version" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_new_version
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_new_version
  methods:
    - POST
  relativeurl: /health_new_version
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_remove_exercise" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_remove_exercise
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_remove_exercise.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_remove_exercise" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_remove_exercise
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_remove_exercise
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_remove_exercise
    description: "Remove an exercise from a training session by index."
    inputSchema: |
      type: object
      properties:
        date:
          type: string
          description: Session date (YYYY-MM-DD)
        exercise_index:
          type: integer
          description: Zero-based index of the exercise to remove
      required:
      - date
      - exercise_index
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_remove_exercise
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_remove_exercise"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_remove_exercise" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_remove_exercise
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_remove_exercise
  methods:
    - POST
  relativeurl: /health_remove_exercise
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_reschedule_session" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_reschedule_session
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_reschedule_session.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_reschedule_session" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_reschedule_session
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_reschedule_session
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_reschedule_session
    description: "Move a training session from one date to another."
    inputSchema: |
      type: object
      properties:
        old_date:
          type: string
          description: Current session date (YYYY-MM-DD)
        new_date:
          type: string
          description: Target date to move to (YYYY-MM-DD)
      required:
      - old_date
      - new_date
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_reschedule_session
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_reschedule_session"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_reschedule_session" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_reschedule_session
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_reschedule_session
  methods:
    - POST
  relativeurl: /health_reschedule_session
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_setup_initialize" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_setup_initialize
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_setup_initialize.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_setup_initialize" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_setup_initialize
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_setup_initialize
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_setup_initialize
    description: "Initialize the first valid current training block for a no-data user."
    inputSchema: |
      type: object
      properties:
        mode:
          type: string
          description: blank, manual_sessions, or template
        program_name:
          type: string
          description: Optional program/block name
        start_date:
          type: string
          description: Program start date (YYYY-MM-DD)
        week_start_day:
          type: string
          description: Week start day, e.g. Monday
        template_sk:
          type: string
          description: Required when mode=template
        maxes:
          type: object
          description: Optional maxes/e1RMs keyed by squat, bench, deadlift, or template
            glossary IDs
      required:
      - mode
      - start_date
      - week_start_day
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_setup_initialize
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_setup_initialize"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_setup_initialize" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_setup_initialize
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_setup_initialize
  methods:
    - POST
  relativeurl: /health_setup_initialize
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_setup_status" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_setup_status
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_setup_status.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_setup_status" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_setup_status
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_setup_status
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_setup_status
    description: "Return no-data onboarding setup state for the active training data partition."
    inputSchema: |
      type: object
      properties: {}
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_setup_status
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_setup_status"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_setup_status" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_setup_status
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_setup_status
  methods:
    - POST
  relativeurl: /health_setup_status
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_snapshot_competition_projection" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_snapshot_competition_projection
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_snapshot_competition_projection.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_snapshot_competition_projection" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_snapshot_competition_projection
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_snapshot_competition_projection
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_snapshot_competition_projection
    description: "Snapshot projected maxes 7 days before a competition and optionally backfill missed snapshots."
    inputSchema: |
      type: object
      properties:
        date:
          type: string
          description: Snapshot date (YYYY-MM-DD)
        version:
          type: string
          description: Program version to update
          default: current
        allow_retrospective:
          type: boolean
          description: Allow backfilling a missed snapshot
          default: false
      required:
      - date
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_snapshot_competition_projection
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_snapshot_competition_projection"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_snapshot_competition_projection" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_snapshot_competition_projection
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_snapshot_competition_projection
  methods:
    - POST
  relativeurl: /health_snapshot_competition_projection
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_update_competition" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_update_competition
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_update_competition.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_update_competition" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_update_competition
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_update_competition
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_update_competition
    description: "Update competition fields by date."
    inputSchema: |
      type: object
      properties:
        date:
          type: string
          description: Competition date to update (YYYY-MM-DD)
        patch:
          type: object
          description: Fields to update (targets, status, notes, etc.)
      required:
      - date
      - patch
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_update_competition
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_update_competition"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_update_competition" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_update_competition
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_update_competition
  methods:
    - POST
  relativeurl: /health_update_competition
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_update_current_maxes" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_update_current_maxes
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_update_current_maxes.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_update_current_maxes" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_update_current_maxes
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_update_current_maxes
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_update_current_maxes
    description: "Update current training maxes."
    inputSchema: |
      type: object
      properties:
        squat_kg:
          type: number
          description: New squat max in kg
        bench_kg:
          type: number
          description: New bench max in kg
        deadlift_kg:
          type: number
          description: New deadlift max in kg
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_update_current_maxes
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_update_current_maxes"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_update_current_maxes" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_update_current_maxes
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_update_current_maxes
  methods:
    - POST
  relativeurl: /health_update_current_maxes
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_update_diet_note" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_update_diet_note
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_update_diet_note.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_update_diet_note" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_update_diet_note
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_update_diet_note
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_update_diet_note
    description: "Create or replace a diet note for a date."
    inputSchema: |
      type: object
      properties:
        date:
          type: string
          description: Date for the diet note (YYYY-MM-DD)
        notes:
          type: string
          description: The diet notes content
      required:
      - date
      - notes
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_update_diet_note
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_update_diet_note"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_update_diet_note" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_update_diet_note
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_update_diet_note
  methods:
    - POST
  relativeurl: /health_update_diet_note
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_update_federation_library" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_update_federation_library
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_update_federation_library.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_update_federation_library" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_update_federation_library
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_update_federation_library
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_update_federation_library
    description: "Replace the shared federation-library document."
    inputSchema: |
      type: object
      properties:
        federations:
          type: array
          items:
            type: object
          description: Complete federation records array
        qualification_standards:
          type: array
          items:
            type: object
          description: Complete qualification standards array
      required:
      - federations
      - qualification_standards
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_update_federation_library
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_update_federation_library"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_update_federation_library" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_update_federation_library
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_update_federation_library
  methods:
    - POST
  relativeurl: /health_update_federation_library
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_update_goals" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_update_goals
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_update_goals.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_update_goals" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_update_goals
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_update_goals
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_update_goals
    description: "Replace the explicit goals array for the current training block."
    inputSchema: |
      type: object
      properties:
        goals:
          type: array
          items:
            type: object
          description: Complete goals array to write to the current block
      required:
      - goals
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_update_goals
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_update_goals"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_update_goals" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_update_goals
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_update_goals
  methods:
    - POST
  relativeurl: /health_update_goals
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_update_meta" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_update_meta
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_update_meta.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_update_meta" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_update_meta
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_update_meta
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_update_meta
    description: "Update program metadata fields, including sex for DOTS calculations."
    inputSchema: |
      type: object
      properties:
        updates:
          type: object
          description: Dict of meta fields to update
      required:
      - updates
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_update_meta
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_update_meta"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_update_meta" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_update_meta
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_update_meta
  methods:
    - POST
  relativeurl: /health_update_meta
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_update_phases" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_update_phases
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_update_phases.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_update_phases" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_update_phases
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_update_phases
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_update_phases
    description: "Replace the full phases list."
    inputSchema: |
      type: object
      properties:
        phases:
          type: array
          items:
            type: object
          description: 'Complete phases list. Each: {name, start_week, end_week, intent}'
      required:
      - phases
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_update_phases
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_update_phases"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_update_phases" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_update_phases
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_update_phases
  methods:
    - POST
  relativeurl: /health_update_phases
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_update_session" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_update_session
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_update_session.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_update_session" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_update_session
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_update_session
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_update_session
    description: "Update fields on an existing training session."
    inputSchema: |
      type: object
      properties:
        date:
          type: string
          description: ISO8601 date string (YYYY-MM-DD) of the session to update
        patch:
          type: object
          description: 'Dict with session fields to update. Allowed keys: completed, session_rpe,
            body_weight_kg, session_notes, exercises'
      required:
      - date
      - patch
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_update_session
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_update_session"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_update_session" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_update_session
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_update_session
  methods:
    - POST
  relativeurl: /health_update_session
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_health_update_supplements" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-health_update_supplements
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: health_update_supplements.zip
YAML
}

resource "kubectl_manifest" "pl_fn_health_update_supplements" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-health_update_supplements
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-health_update_supplements
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: health_update_supplements
    description: "Update the supplement protocol."
    inputSchema: |
      type: object
      properties:
        patch:
          type: object
          description: '{"supplements": [...]} or {"supplement_phases": [...]}'
      required:
      - patch
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-health_update_supplements
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "health_update_supplements"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_health_update_supplements" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-health_update_supplements
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-health_update_supplements
  methods:
    - POST
  relativeurl: /health_update_supplements
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_import_apply" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-import_apply
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: import_apply.zip
YAML
}

resource "kubectl_manifest" "pl_fn_import_apply" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-import_apply
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-import_apply
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: import_apply
    description: "Apply a staged import to the program or template library."
    inputSchema: |
      type: object
      properties:
        import_id:
          type: string
        merge_strategy:
          type: string
          default: append
        conflict_resolutions:
          type: array
          items:
            type: object
        start_date:
          type: string
      required:
      - import_id
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-import_apply
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "import_apply"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_import_apply" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-import_apply
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-import_apply
  methods:
    - POST
  relativeurl: /import_apply
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_import_get_pending" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-import_get_pending
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: import_get_pending.zip
YAML
}

resource "kubectl_manifest" "pl_fn_import_get_pending" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-import_get_pending
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-import_get_pending
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: import_get_pending
    description: "Get a single pending import by ID."
    inputSchema: |
      type: object
      properties:
        import_id:
          type: string
      required:
      - import_id
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-import_get_pending
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "import_get_pending"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_import_get_pending" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-import_get_pending
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-import_get_pending
  methods:
    - POST
  relativeurl: /import_get_pending
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_import_list_pending" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-import_list_pending
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: import_list_pending.zip
YAML
}

resource "kubectl_manifest" "pl_fn_import_list_pending" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-import_list_pending
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-import_list_pending
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: import_list_pending
    description: "List all awaiting_review imports."
    inputSchema: |
      type: object
      properties:
        import_type:
          type: string
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-import_list_pending
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "import_list_pending"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_import_list_pending" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-import_list_pending
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-import_list_pending
  methods:
    - POST
  relativeurl: /import_list_pending
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_import_parse_file" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-import_parse_file
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: import_parse_file.zip
YAML
}

resource "kubectl_manifest" "pl_fn_import_parse_file" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-import_parse_file
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-import_parse_file
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 1
            SpecializationTimeout: 120
            TargetCPUPercent: 70
  tool:
    name: import_parse_file
    description: "Parse a spreadsheet file and stage it as a pending import."
    inputSchema: |
      type: object
      properties:
        base64_content:
          type: string
        filename:
          type: string
      required:
      - base64_content
      - filename
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-import_parse_file
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: ANALYSIS_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: ESTIMATE_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: IMPORT_FAST_MODEL
              value: "anthropic/claude-haiku-4.5"
            - name: GLOSSARY_TEXT_MODEL
              value: "google/gemini-3.1-flash-lite"
            - name: IF_TOOL_NAME
              value: "import_parse_file"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1024Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_import_parse_file" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-import_parse_file
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-import_parse_file
  methods:
    - POST
  relativeurl: /import_parse_file
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_import_reject" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-import_reject
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: import_reject.zip
YAML
}

resource "kubectl_manifest" "pl_fn_import_reject" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-import_reject
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-import_reject
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: import_reject
    description: "Reject a staged import."
    inputSchema: |
      type: object
      properties:
        import_id:
          type: string
        reason:
          type: string
      required:
      - import_id
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-import_reject
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "import_reject"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_import_reject" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-import_reject
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-import_reject
  methods:
    - POST
  relativeurl: /import_reject
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_ipf_weight_classes" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-ipf_weight_classes
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: ipf_weight_classes.zip
YAML
}

resource "kubectl_manifest" "pl_fn_ipf_weight_classes" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-ipf_weight_classes
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-ipf_weight_classes
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: ipf_weight_classes
    description: "Get IPF weight classes for a given sex."
    inputSchema: |
      type: object
      properties:
        sex:
          type: string
          description: 'Sex: ''M'' or ''F'''
      required:
      - sex
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-ipf_weight_classes
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "ipf_weight_classes"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 128Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_ipf_weight_classes" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-ipf_weight_classes
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-ipf_weight_classes
  methods:
    - POST
  relativeurl: /ipf_weight_classes
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_kg_to_lb" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-kg_to_lb
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: kg_to_lb.zip
YAML
}

resource "kubectl_manifest" "pl_fn_kg_to_lb" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-kg_to_lb
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-kg_to_lb
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: kg_to_lb
    description: "Convert kilograms to pounds."
    inputSchema: |
      type: object
      properties:
        kg:
          type: number
          description: Weight in kilograms
      required:
      - kg
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-kg_to_lb
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "kg_to_lb"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 128Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_kg_to_lb" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-kg_to_lb
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-kg_to_lb
  methods:
    - POST
  relativeurl: /kg_to_lb
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_lb_to_kg" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-lb_to_kg
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: lb_to_kg.zip
YAML
}

resource "kubectl_manifest" "pl_fn_lb_to_kg" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-lb_to_kg
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-lb_to_kg
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: lb_to_kg
    description: "Convert pounds to kilograms."
    inputSchema: |
      type: object
      properties:
        lb:
          type: number
          description: Weight in pounds
      required:
      - lb
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-lb_to_kg
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "lb_to_kg"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 128Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_lb_to_kg" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-lb_to_kg
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-lb_to_kg
  methods:
    - POST
  relativeurl: /lb_to_kg
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_lift_profile_estimate_stimulus" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-lift_profile_estimate_stimulus
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: lift_profile_estimate_stimulus.zip
YAML
}

resource "kubectl_manifest" "pl_fn_lift_profile_estimate_stimulus" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-lift_profile_estimate_stimulus
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-lift_profile_estimate_stimulus
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 1
            SpecializationTimeout: 120
            TargetCPUPercent: 70
  tool:
    name: lift_profile_estimate_stimulus
    description: "Estimate a 1-2 INOL stimulus coefficient from an existing lift profile. Requires profile completeness score >= 55."
    inputSchema: |
      type: object
      properties:
        profile:
          type: object
          description: Lift profile with lift, style_notes, sticking_points, primary_muscle,
            and volume_tolerance.
      required:
      - profile
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-lift_profile_estimate_stimulus
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: ANALYSIS_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: ESTIMATE_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: IMPORT_FAST_MODEL
              value: "anthropic/claude-haiku-4.5"
            - name: GLOSSARY_TEXT_MODEL
              value: "google/gemini-3.1-flash-lite"
            - name: IF_TOOL_NAME
              value: "lift_profile_estimate_stimulus"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_lift_profile_estimate_stimulus" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-lift_profile_estimate_stimulus
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-lift_profile_estimate_stimulus
  methods:
    - POST
  relativeurl: /lift_profile_estimate_stimulus
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_lift_profile_review" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-lift_profile_review
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: lift_profile_review.zip
YAML
}

resource "kubectl_manifest" "pl_fn_lift_profile_review" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-lift_profile_review
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-lift_profile_review
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 1
            SpecializationTimeout: 120
            TargetCPUPercent: 70
  tool:
    name: lift_profile_review
    description: "Review a squat, bench, or deadlift style profile and return missing biomechanical details needed to estimate a lift-specific INOL stimulus coefficient."
    inputSchema: |
      type: object
      properties:
        profile:
          type: object
          description: Lift profile with lift, style_notes, sticking_points, primary_muscle,
            and volume_tolerance.
      required:
      - profile
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-lift_profile_review
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: ANALYSIS_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: ESTIMATE_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: IMPORT_FAST_MODEL
              value: "anthropic/claude-haiku-4.5"
            - name: GLOSSARY_TEXT_MODEL
              value: "google/gemini-3.1-flash-lite"
            - name: IF_TOOL_NAME
              value: "lift_profile_review"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_lift_profile_review" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-lift_profile_review
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-lift_profile_review
  methods:
    - POST
  relativeurl: /lift_profile_review
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_lift_profile_rewrite" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-lift_profile_rewrite
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: lift_profile_rewrite.zip
YAML
}

resource "kubectl_manifest" "pl_fn_lift_profile_rewrite" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-lift_profile_rewrite
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-lift_profile_rewrite
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 1
            SpecializationTimeout: 120
            TargetCPUPercent: 70
  tool:
    name: lift_profile_rewrite
    description: "Rewrite lift profile text for analysis clarity without estimating stimulus coefficient."
    inputSchema: |
      type: object
      properties:
        profile:
          type: object
          description: Lift profile with lift, style_notes, sticking_points, primary_muscle,
            and volume_tolerance.
      required:
      - profile
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-lift_profile_rewrite
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: ANALYSIS_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: ESTIMATE_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: IMPORT_FAST_MODEL
              value: "anthropic/claude-haiku-4.5"
            - name: GLOSSARY_TEXT_MODEL
              value: "google/gemini-3.1-flash-lite"
            - name: IF_TOOL_NAME
              value: "lift_profile_rewrite"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_lift_profile_rewrite" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-lift_profile_rewrite
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-lift_profile_rewrite
  methods:
    - POST
  relativeurl: /lift_profile_rewrite
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_lift_profile_rewrite_and_estimate" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-lift_profile_rewrite_and_estimate
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: lift_profile_rewrite_and_estimate.zip
YAML
}

resource "kubectl_manifest" "pl_fn_lift_profile_rewrite_and_estimate" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-lift_profile_rewrite_and_estimate
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-lift_profile_rewrite_and_estimate
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: lift_profile_rewrite_and_estimate
    description: "Rewrite a lift style profile for analysis clarity and estimate a 1-2 INOL stimulus coefficient against a baseline of 1.0."
    inputSchema: |
      type: object
      properties:
        profile:
          type: object
          description: Lift profile with lift, style_notes, sticking_points, primary_muscle,
            and volume_tolerance.
      required:
      - profile
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-lift_profile_rewrite_and_estimate
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "lift_profile_rewrite_and_estimate"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1024Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_lift_profile_rewrite_and_estimate" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-lift_profile_rewrite_and_estimate
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-lift_profile_rewrite_and_estimate
  methods:
    - POST
  relativeurl: /lift_profile_rewrite_and_estimate
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_master_sync" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-master-sync
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: master-sync.zip
YAML
}

resource "kubectl_manifest" "pl_fn_master_sync" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-master-sync
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-master-sync
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: master-sync
    description: "master-sync"
    inputSchema: |
      type: object
      properties: {}
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-master-sync
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "master-sync"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_master_sync" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-master-sync
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-master-sync
  methods:
    - POST
  relativeurl: /master-sync
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_multi_block_comparison_analysis" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-multi_block_comparison_analysis
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: multi_block_comparison_analysis.zip
YAML
}

resource "kubectl_manifest" "pl_fn_multi_block_comparison_analysis" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-multi_block_comparison_analysis
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-multi_block_comparison_analysis
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: multi_block_comparison_analysis
    description: "AI comparison of current and historical block analysis bundles. Identifies similarities, differences, lift-specific outcomes, ROI, volume dose response, bodyweight/training-day relationships, projection accuracy, fatigue patterns, and best-value blocks."
    inputSchema: |
      type: object
      properties:
        payload:
          type: object
          description: Multi-block comparison payload built from block analytics.
      required:
      - payload
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-multi_block_comparison_analysis
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "multi_block_comparison_analysis"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_multi_block_comparison_analysis" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-multi_block_comparison_analysis
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-multi_block_comparison_analysis
  methods:
    - POST
  relativeurl: /multi_block_comparison_analysis
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_muscle_group_estimate" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-muscle_group_estimate
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: muscle_group_estimate.zip
YAML
}

resource "kubectl_manifest" "pl_fn_muscle_group_estimate" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-muscle_group_estimate
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-muscle_group_estimate
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 1
            SpecializationTimeout: 120
            TargetCPUPercent: 70
  tool:
    name: muscle_group_estimate
    description: "Estimate the primary, secondary, and tertiary muscle groups for an exercise using AI analysis of the movement and the user's lift profiles."
    inputSchema: |
      type: object
      properties:
        exercise:
          type: object
          description: Exercise metadata dict
          properties:
            name:
              type: string
            category:
              type: string
            equipment:
              type: string
            primary_muscles:
              type: array
              items:
                type: string
            secondary_muscles:
              type: array
              items:
                type: string
            tertiary_muscles:
              type: array
              items:
                type: string
            description:
              type: string
            how_to_perform:
              type: string
            why_do_it:
              type: string
        lift_profiles:
          type: array
          description: Optional squat/bench/deadlift lift profiles to pass through to the
            estimator
          items:
            type: object
            properties:
              lift:
                type: string
              style_notes:
                type: string
              sticking_points:
                type: string
              primary_muscle:
                type: string
              volume_tolerance:
                type: string
      required:
      - exercise
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-muscle_group_estimate
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: ANALYSIS_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: ESTIMATE_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: IMPORT_FAST_MODEL
              value: "anthropic/claude-haiku-4.5"
            - name: GLOSSARY_TEXT_MODEL
              value: "google/gemini-3.1-flash-lite"
            - name: IF_TOOL_NAME
              value: "muscle_group_estimate"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_muscle_group_estimate" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-muscle_group_estimate
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-muscle_group_estimate
  methods:
    - POST
  relativeurl: /muscle_group_estimate
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_pct_of_max" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-pct_of_max
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: pct_of_max.zip
YAML
}

resource "kubectl_manifest" "pl_fn_pct_of_max" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-pct_of_max
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-pct_of_max
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: pct_of_max
    description: "Calculate a percentage of a max weight."
    inputSchema: |
      type: object
      properties:
        max_kg:
          type: number
          description: Maximum weight in kg
        pct:
          type: number
          description: Percentage (0-150, not 0-1)
      required:
      - max_kg
      - pct
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-pct_of_max
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "pct_of_max"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 128Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_pct_of_max" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-pct_of_max
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-pct_of_max
  methods:
    - POST
  relativeurl: /pct_of_max
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_powerlifting_filter_categories" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-powerlifting_filter_categories
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: powerlifting_filter_categories.zip
YAML
}

resource "kubectl_manifest" "pl_fn_powerlifting_filter_categories" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-powerlifting_filter_categories
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-powerlifting_filter_categories
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 2
            SpecializationTimeout: 120
            TargetCPUPercent: 80
  tool:
    name: powerlifting_filter_categories
    description: "Retrieves the unique options available for filtering the OpenPowerlifting dataset."
    inputSchema: |
      type: object
      properties: {}
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-powerlifting_filter_categories
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: POWERLIFTING_S3_BUCKET
              value: "${var.powerlifting_s3_bucket}"
            - name: IF_TOOL_NAME
              value: "powerlifting_filter_categories"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_powerlifting_filter_categories" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-powerlifting_filter_categories
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-powerlifting_filter_categories
  methods:
    - POST
  relativeurl: /powerlifting_filter_categories
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_powerlifting_ranking_percentile" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-powerlifting_ranking_percentile
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: powerlifting_ranking_percentile.zip
YAML
}

resource "kubectl_manifest" "pl_fn_powerlifting_ranking_percentile" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-powerlifting_ranking_percentile
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-powerlifting_ranking_percentile
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 2
            SpecializationTimeout: 120
            TargetCPUPercent: 80
  tool:
    name: powerlifting_ranking_percentile
    description: "Returns national/regional/global top-percentile cards for the dashboard. Filters the OpenPowerlifting dataset to the 3 nearest IPF weight classes, last 3 calendar years, deduplicated by lifter (best total per name). Returns percentile (0-100) for Squat/Bench/Deadlift/Total across global, national (country), and regional (country+region) scopes. A value is null when <10 comparison lifters or the lift was not provided."
    inputSchema: |
      type: object
      properties:
        squat_kg:
          type: number
          description: User's best squat in kg
        bench_kg:
          type: number
          description: User's best bench in kg
        deadlift_kg:
          type: number
          description: User's best deadlift in kg
        bodyweight_kg:
          type: number
          description: User's bodyweight in kg
        sex_code:
          type: string
          description: '''M'' or ''F'''
        country:
          type: string
          description: Filter national scope (MeetCountry value from dataset)
        region:
          type: string
          description: Filter regional scope (State value from dataset)
        age_class:
          type: string
          description: Filter by age class
        equipment:
          type: string
          description: Filter by equipment (e.g. Raw)
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-powerlifting_ranking_percentile
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: POWERLIFTING_S3_BUCKET
              value: "${var.powerlifting_s3_bucket}"
            - name: IF_TOOL_NAME
              value: "powerlifting_ranking_percentile"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_powerlifting_ranking_percentile" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-powerlifting_ranking_percentile
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-powerlifting_ranking_percentile
  methods:
    - POST
  relativeurl: /powerlifting_ranking_percentile
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_program_archive" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-program_archive
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: program_archive.zip
YAML
}

resource "kubectl_manifest" "pl_fn_program_archive" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-program_archive
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-program_archive
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: program_archive
    description: "Archive a program version."
    inputSchema: |
      type: object
      properties:
        sk:
          type: string
      required:
      - sk
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-program_archive
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "program_archive"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_program_archive" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-program_archive
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-program_archive
  methods:
    - POST
  relativeurl: /program_archive
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_program_evaluation" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-program_evaluation
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: program_evaluation.zip
YAML
}

resource "kubectl_manifest" "pl_fn_program_evaluation" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-program_evaluation
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-program_evaluation
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 1
            SpecializationTimeout: 120
            TargetCPUPercent: 70
  tool:
    name: program_evaluation
    description: "Full-block AI program evaluation by a sports scientist. Evaluates the current block against competition goals, identifies what is working and not, and suggests small targeted changes. Requires >= 4 completed weeks. Cached weekly. Use refresh=true to force regeneration."
    inputSchema: |
      type: object
      properties:
        refresh:
          type: boolean
          description: Force regeneration, ignore cache
          default: false
        cache_only:
          type: boolean
          description: Return only cached results without generating AI output
          default: false
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-program_evaluation
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: ANALYSIS_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: ESTIMATE_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: IMPORT_FAST_MODEL
              value: "anthropic/claude-haiku-4.5"
            - name: GLOSSARY_TEXT_MODEL
              value: "google/gemini-3.1-flash-lite"
            - name: IF_TOOL_NAME
              value: "program_evaluation"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_program_evaluation" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-program_evaluation
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-program_evaluation
  methods:
    - POST
  relativeurl: /program_evaluation
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_program_unarchive" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-program_unarchive
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: program_unarchive.zip
YAML
}

resource "kubectl_manifest" "pl_fn_program_unarchive" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-program_unarchive
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-program_unarchive
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: program_unarchive
    description: "Unarchive a program version."
    inputSchema: |
      type: object
      properties:
        sk:
          type: string
      required:
      - sk
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-program_unarchive
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "program_unarchive"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_program_unarchive" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-program_unarchive
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-program_unarchive
  methods:
    - POST
  relativeurl: /program_unarchive
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_regenerate_analysis" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-regenerate_analysis
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: regenerate_analysis.zip
YAML
}

resource "kubectl_manifest" "pl_fn_regenerate_analysis" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-regenerate_analysis
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-regenerate_analysis
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: regenerate_analysis
    description: "Regenerate deterministic current-block analysis caches: 6 weekly windows and the markdown export. Call this when the operator asks to refresh or regenerate their training analysis. This intentionally does not regenerate AI correlation reports, AI program evaluation, past-block caches, or the lifetime compare AI cache."
    inputSchema: |
      type: object
      properties: {}
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-regenerate_analysis
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "regenerate_analysis"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_regenerate_analysis" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-regenerate_analysis
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-regenerate_analysis
  methods:
    - POST
  relativeurl: /regenerate_analysis
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_template_apply" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-template_apply
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: template_apply.zip
YAML
}

resource "kubectl_manifest" "pl_fn_template_apply" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-template_apply
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-template_apply
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: template_apply
    description: "Apply a template to the program block (preview)."
    inputSchema: |
      type: object
      properties:
        sk:
          type: string
        target:
          type: string
          default: new_block
        start_date:
          type: string
        week_start_day:
          type: string
          default: Monday
        actor_pk:
          type: string
          description: Signed-in user/template author partition for draft visibility
      required:
      - sk
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-template_apply
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "template_apply"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_template_apply" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-template_apply
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-template_apply
  methods:
    - POST
  relativeurl: /template_apply
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_template_apply_confirm" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-template_apply_confirm
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: template_apply_confirm.zip
YAML
}

resource "kubectl_manifest" "pl_fn_template_apply_confirm" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-template_apply_confirm
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-template_apply_confirm
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: template_apply_confirm
    description: "Confirm and write concretized block from template."
    inputSchema: |
      type: object
      properties:
        sk:
          type: string
        backfilled_maxes:
          type: object
        start_date:
          type: string
        week_start_day:
          type: string
        target:
          type: string
          description: Apply strategy
          default: new_block
        actor_pk:
          type: string
          description: Signed-in user/template author partition for draft visibility
      required:
      - sk
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-template_apply_confirm
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "template_apply_confirm"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_template_apply_confirm" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-template_apply_confirm
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-template_apply_confirm
  methods:
    - POST
  relativeurl: /template_apply_confirm
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_template_archive" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-template_archive
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: template_archive.zip
YAML
}

resource "kubectl_manifest" "pl_fn_template_archive" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-template_archive
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-template_archive
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: template_archive
    description: "Archive a template."
    inputSchema: |
      type: object
      properties:
        sk:
          type: string
        actor_pk:
          type: string
          description: Signed-in user/template author partition
      required:
      - sk
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-template_archive
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "template_archive"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_template_archive" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-template_archive
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-template_archive
  methods:
    - POST
  relativeurl: /template_archive
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_template_copy" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-template_copy
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: template_copy.zip
YAML
}

resource "kubectl_manifest" "pl_fn_template_copy" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-template_copy
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-template_copy
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: template_copy
    description: "Duplicate a template."
    inputSchema: |
      type: object
      properties:
        sk:
          type: string
        new_name:
          type: string
        actor_pk:
          type: string
          description: Signed-in user/template author partition
        author:
          type: string
          description: Display author
      required:
      - sk
      - new_name
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-template_copy
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "template_copy"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_template_copy" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-template_copy
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-template_copy
  methods:
    - POST
  relativeurl: /template_copy
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_template_create_blank" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-template_create_blank
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: template_create_blank.zip
YAML
}

resource "kubectl_manifest" "pl_fn_template_create_blank" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-template_create_blank
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-template_create_blank
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: template_create_blank
    description: "Create a new blank training template with no sessions."
    inputSchema: |
      type: object
      properties:
        name:
          type: string
        description:
          type: string
          default: ''
        estimated_weeks:
          type: integer
          default: 4
        days_per_week:
          type: integer
          default: 3
        actor_pk:
          type: string
          description: Signed-in user/template author partition
        author:
          type: string
          description: Display author
      required:
      - name
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-template_create_blank
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "template_create_blank"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_template_create_blank" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-template_create_blank
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-template_create_blank
  methods:
    - POST
  relativeurl: /template_create_blank
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_template_create_from_block" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-template_create_from_block
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: template_create_from_block.zip
YAML
}

resource "kubectl_manifest" "pl_fn_template_create_from_block" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-template_create_from_block
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-template_create_from_block
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: template_create_from_block
    description: "Convert program block to template."
    inputSchema: |
      type: object
      properties:
        name:
          type: string
        program_sk:
          type: string
        actor_pk:
          type: string
          description: Signed-in user/template author partition
        author:
          type: string
          description: Display author
      required:
      - name
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-template_create_from_block
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "template_create_from_block"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_template_create_from_block" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-template_create_from_block
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-template_create_from_block
  methods:
    - POST
  relativeurl: /template_create_from_block
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_template_create_from_payload" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-template_create_from_payload
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: template_create_from_payload.zip
YAML
}

resource "kubectl_manifest" "pl_fn_template_create_from_payload" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-template_create_from_payload
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-template_create_from_payload
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: template_create_from_payload
    description: "Create a complete reusable training template atomically from a structured payload."
    inputSchema: |
      type: object
      properties:
        template:
          type: object
        actor_pk:
          type: string
          description: Signed-in user/template author partition
        author:
          type: string
          description: Display author
        published:
          type: boolean
          default: false
        import_job_id:
          type: string
      required:
      - template
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-template_create_from_payload
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "template_create_from_payload"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_template_create_from_payload" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-template_create_from_payload
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-template_create_from_payload
  methods:
    - POST
  relativeurl: /template_create_from_payload
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_template_evaluate" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-template_evaluate
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: template_evaluate.zip
YAML
}

resource "kubectl_manifest" "pl_fn_template_evaluate" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-template_evaluate
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-template_evaluate
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 1
            SpecializationTimeout: 120
            TargetCPUPercent: 70
  tool:
    name: template_evaluate
    description: "Run AI-powered template evaluation."
    inputSchema: |
      type: object
      properties:
        sk:
          type: string
        actor_pk:
          type: string
          description: Signed-in user/template author partition for draft visibility
      required:
      - sk
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-template_evaluate
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: ANALYSIS_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: ESTIMATE_MODEL
              value: "anthropic/claude-sonnet-4.6"
            - name: IMPORT_FAST_MODEL
              value: "anthropic/claude-haiku-4.5"
            - name: GLOSSARY_TEXT_MODEL
              value: "google/gemini-3.1-flash-lite"
            - name: IF_TOOL_NAME
              value: "template_evaluate"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_template_evaluate" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-template_evaluate
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-template_evaluate
  methods:
    - POST
  relativeurl: /template_evaluate
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_template_get" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-template_get
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: template_get.zip
YAML
}

resource "kubectl_manifest" "pl_fn_template_get" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-template_get
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-template_get
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 1
            MaxScale: 2
            SpecializationTimeout: 60
            TargetCPUPercent: 70
  tool:
    name: template_get
    description: "Get full training template structure."
    inputSchema: |
      type: object
      properties:
        sk:
          type: string
        actor_pk:
          type: string
          description: Signed-in user/template author partition for draft visibility
      required:
      - sk
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-template_get
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "template_get"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_template_get" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-template_get
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-template_get
  methods:
    - POST
  relativeurl: /template_get
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_template_list" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-template_list
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: template_list.zip
YAML
}

resource "kubectl_manifest" "pl_fn_template_list" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-template_list
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-template_list
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 1
            MaxScale: 2
            SpecializationTimeout: 60
            TargetCPUPercent: 70
  tool:
    name: template_list
    description: "List all training templates."
    inputSchema: |
      type: object
      properties:
        include_archived:
          type: boolean
          default: false
        actor_pk:
          type: string
          description: Signed-in user/template author partition for draft visibility
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-template_list
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "template_list"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_template_list" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-template_list
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-template_list
  methods:
    - POST
  relativeurl: /template_list
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_template_publish" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-template_publish
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: template_publish.zip
YAML
}

resource "kubectl_manifest" "pl_fn_template_publish" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-template_publish
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-template_publish
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: template_publish
    description: "Publish an authored draft template so everyone can see and apply it."
    inputSchema: |
      type: object
      properties:
        sk:
          type: string
        actor_pk:
          type: string
          description: Signed-in user/template author partition
      required:
      - sk
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-template_publish
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "template_publish"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_template_publish" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-template_publish
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-template_publish
  methods:
    - POST
  relativeurl: /template_publish
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_template_unarchive" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-template_unarchive
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: template_unarchive.zip
YAML
}

resource "kubectl_manifest" "pl_fn_template_unarchive" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-template_unarchive
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-template_unarchive
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: template_unarchive
    description: "Unarchive a template."
    inputSchema: |
      type: object
      properties:
        sk:
          type: string
        actor_pk:
          type: string
          description: Signed-in user/template author partition
      required:
      - sk
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-template_unarchive
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "template_unarchive"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_template_unarchive" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-template_unarchive
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-template_unarchive
  methods:
    - POST
  relativeurl: /template_unarchive
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_template_unpublish" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-template_unpublish
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: template_unpublish.zip
YAML
}

resource "kubectl_manifest" "pl_fn_template_unpublish" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-template_unpublish
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-template_unpublish
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: template_unpublish
    description: "Unpublish an authored template so only its author can see it."
    inputSchema: |
      type: object
      properties:
        sk:
          type: string
        actor_pk:
          type: string
          description: Signed-in user/template author partition
      required:
      - sk
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-template_unpublish
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "template_unpublish"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_template_unpublish" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-template_unpublish
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-template_unpublish
  methods:
    - POST
  relativeurl: /template_unpublish
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_template_update" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-template_update
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: template_update.zip
YAML
}

resource "kubectl_manifest" "pl_fn_template_update" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-template_update
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-template_update
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: template_update
    description: "Overwrite an existing training template in place (metadata, phases, sessions)."
    inputSchema: |
      type: object
      properties:
        sk:
          type: string
        template:
          type: object
        actor_pk:
          type: string
          description: Signed-in user/template author partition
      required:
      - sk
      - template
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-template_update
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "template_update"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 256Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_template_update" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-template_update
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-template_update
  methods:
    - POST
  relativeurl: /template_update
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_weekly_analysis" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-weekly_analysis
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  buildcmd: /usr/local/bin/build
  source:
    type: literal
    literal: weekly_analysis.zip
YAML
}

resource "kubectl_manifest" "pl_fn_weekly_analysis" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-fn-weekly_analysis
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-weekly_analysis
      namespace: if-portals
  functionTimeout: 900
  concurrency: 500
        InvokeStrategy:
          StrategyType: execution
          ExecutionStrategy:
            ExecutorType: newdeploy
            MinScale: 0
            MaxScale: 3
            SpecializationTimeout: 90
            TargetCPUPercent: 70
  tool:
    name: weekly_analysis
    description: "Full weekly training analysis — progression, RPE drift, fatigue index, compliance, meet projection. Returns structured JSON."
    inputSchema: |
      type: object
      properties:
        weeks:
          type: integer
          description: Number of weeks to analyze
          default: 1
        block:
          type: string
          description: Program block filter
          default: current
        week_start:
          type: integer
          description: Inclusive training week number to start analysis
        week_end:
          type: integer
          description: Inclusive training week number to end analysis
        window_start:
          type: string
          description: Optional date window start (YYYY-MM-DD) for time-series context
        window_end:
          type: string
          description: Optional date window end (YYYY-MM-DD) for time-series context
        ref_date:
          type: string
          description: Optional reference date (YYYY-MM-DD)
        refresh_program:
          type: boolean
          description: Invalidate the program cache before analysis
          default: true
        program:
          type: object
          description: Optional program snapshot supplied by the caller
        sessions:
          type: array
          description: Optional session snapshot supplied by the caller
          items:
            type: object
      required: []
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-weekly_analysis
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
            - name: IF_AWS_REGION
              value: "ca-central-1"
            - name: IF_HEALTH_TABLE_NAME
              value: "if-health"
            - name: IF_TEMPLATES_TABLE_NAME
              value: "if-health-templates"
            - name: IF_SESSIONS_TABLE_NAME
              value: "if-sessions"
            - name: IF_ANALYSIS_CACHE_TABLE_NAME
              value: "if-powerlifting-analysis-cache"
            - name: HEALTH_PROGRAM_PK
              value: "operator"
            - name: LLM_BASE_URL
              value: "https://openrouter.ai/api/v1"
            - name: IF_TOOL_NAME
              value: "weekly_analysis"
          envFrom:
            - secretRef:
                name: pl-fission-secrets
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi
    volumes: []
YAML
}

resource "kubectl_manifest" "pl_ht_weekly_analysis" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: HTTPTrigger
metadata:
  name: pl-ht-weekly_analysis
  namespace: if-portals
spec:
  functionref:
    type: name
    name: pl-fn-weekly_analysis
  methods:
    - POST
  relativeurl: /weekly_analysis
  prefn:
    - name: pl-authorizer
      namespace: if-portals
YAML
}

resource "kubectl_manifest" "pl_pkg_pl_authorizer" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Package
metadata:
  name: pl-pkg-pl-authorizer
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  source:
    type: literal
    literal: pl_authorizer.zip
YAML
}

resource "kubectl_manifest" "pl_fn_pl_authorizer" {
  server_side_apply = true
  force_conflicts   = true
  yaml_body         = <<-YAML
apiVersion: fission.io/v1
kind: Function
metadata:
  name: pl-authorizer
  namespace: if-portals
spec:
  environment:
    name: pl-fission-tools
    namespace: fission
  package:
    packageref:
      name: pl-pkg-pl-authorizer
      namespace: if-portals
  functionTimeout: 5
  InvokeStrategy:
    StrategyType: execution
    ExecutionStrategy:
      ExecutorType: newdeploy
      MinScale: 0
      MaxScale: 1
      SpecializationTimeout: 30
      TargetCPUPercent: 70
  podspec:
    serviceAccountName: default
    containers:
      - name: pl-authorizer
        image: ghcr.io/fission/python-env
        imagePullPolicy: IfNotPresent
        env:
          - name: IF_TOOL_NAME
            value: "pl_authorizer"
          - name: INTERNAL_API_TOKEN
            valueFrom:
              secretKeyRef:
                name: pl-fission-secrets
                key: INTERNAL_API_TOKEN
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            cpu: 200m
            memory: 128Mi
    volumes: []
YAML
}

