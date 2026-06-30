variable "fission_enabled" {
  description = "Install Fission and provision the OpenCode job-pod environment / function / trigger. Disable to skip the Fission install for environments that don't need it."
  type        = bool
  default     = true
}

variable "fission_version" {
  description = "Fission helm chart and CRD version. Must match a published chart at https://fission.github.io/fission-charts/. k3s 1.27+ supports 1.20.x; 1.25+ requires k8s 1.32+."
  type        = string
  default     = "1.26.0"
}

variable "fission_namespace" {
  description = "Kubernetes namespace where the Fission controller, router, executor, etc. are installed."
  type        = string
  default     = "fission"
}

variable "fission_function_namespace" {
  description = "Namespace where the Fission Function and HTTPTrigger for the opencode runner live. Must be if-portals so the function pod can mount the if-agent-* PVCs the IF agent pod uses."
  type        = string
  default     = "if-portals"
}

variable "fission_environment_name" {
  description = "Fission Environment resource name (base image + runtime for newdeploy function pods)."
  type        = string
  default     = "opencode-runner"
}

variable "fission_function_name" {
  description = "Fission Function resource name for the opencode job pod."
  type        = string
  default     = "opencode-job"
}

variable "fission_http_trigger_url" {
  description = "URL path the Fission HTTP trigger listens on. Must match the path the IF agent API posts to and the opencode-runner handles (POST /v1/opencode/execute). The router forwards this path verbatim to the function pod."
  type        = string
  default     = "/v1/opencode/execute"
}

variable "fission_router_timeout_seconds" {
  description = "Fission router HTTP timeout in seconds. Long OpenCode jobs need a generous timeout."
  type        = number
  default     = 1800
}

variable "opencode_runner_memory_mb" {
  description = "Memory limit for each Fission-spawned OpenCode job pod."
  type        = number
  default     = 5120
}

variable "opencode_runner_memory_request_mb" {
  description = "Memory request for each Fission-spawned OpenCode job pod."
  type        = number
  default     = 2048
}

variable "opencode_runner_cpu_millicores" {
  description = "CPU limit for each Fission-spawned OpenCode job pod."
  type        = number
  default     = 2000
}

variable "opencode_runner_cpu_request_millicores" {
  description = "CPU request for each Fission-spawned OpenCode job pod."
  type        = number
  default     = 1000
}

variable "opencode_runner_max_concurrent" {
  description = "Maximum concurrent OpenCode job pods the Fission newdeploy executor can run. Scales the function Deployment up to this many replicas."
  type        = number
  default     = 6
}