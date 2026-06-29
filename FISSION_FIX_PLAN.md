# Fission Fix Plan — Powerlifting Tools + OpenCode Runner

> Audience: an intermediate/junior engineer implementing this end to end.
> Author: senior handoff. Everything you need is here; you should not need to
> do additional research. Follow the sections in order. **Read the
> "Guardrails" section before touching anything.**

---

## 0. TL;DR — what is broken and why

There are **two** separate Fission problems in this monorepo. Both currently
result in "no response" when the UI/agent calls them.

### Problem A — Powerlifting tool functions never get their Python deps
The powerlifting backend (`utils/powerlifting-app/backend`) calls 94 health
tools through the Fission router at
`http://router.fission.svc.cluster.local:80/<tool>`. Each tool is a Fission
Function. **They never start** because their Python dependencies
(`boto3`, `pandas`, `httpx`, `jinja2`, `scipy`, `chromadb`) are never
installed.

Root cause: in `terraform/k8s-fission-powerlifting.tf` the `pl_packages`
resource ships each zip as a **deployment archive**
(`deployment = { type = "literal", ... }`). A deployment archive tells Fission
"this is already built, run it as-is" — **the Fission builder is skipped, so
`pip install -r requirements.txt` never runs.** Confirmed live: every package
shows `BUILDSTATUS: none`, and the function newdeploy pods fail readiness
(`:8000 connection refused`) because the handler crashes on
`import boto3`.

To make Fission auto-install deps (what we want — NO baking deps into an
image), the package must be a **source archive** (`spec.source`) **plus a
`spec.buildcmd`** that runs pip. Then the `python-builder` builds each package
once.

### Problem B — OpenCode runner uses the wrong Fission model
The IF agent API calls the OpenCode runner through the same router at
`POST /v1/opencode/execute`. It also returns no response (a live curl hangs
and times out).

Root causes:
1. The Function uses `ExecutorType: container`, but the Rust server
   (`utils/opencode-runner/src/main.rs`) is a **one-shot** server: it serves
   exactly one job, then exits. The container executor expects a
   **long-running** HTTP service; when the process exits, the pod is treated
   as crashed and the endpoint hangs.
2. `MinScale: 0` + a **591 MB image with a ~42s cold pull** blows the
   round-trip on every cold request.
3. No readiness probe.

**Decision (from the owner): implement Option B.** Re-model OpenCode exactly
like the powerlifting functions: a **newdeploy** Function on a **custom Fission
Environment image**, with the Rust server rewritten to implement Fission's
strict environment HTTP protocol (`/healthz`, `/specialize`, `/v2/specialize`,
catch-all `/`) and stay alive across requests.

---

## 1. Guardrails (DO NOT SKIP)

From the repo operational rules — violating these breaks the cluster or loses
data:

- **Never** run `terraform apply`/`destroy` yourself except a targeted
  `terraform apply -target=...`, and only after the owner explicitly approves.
  This plan lists the exact targeted applies; present them, do not auto-run.
- **Never** run mutating `kubectl` (`delete/apply/patch/edit/scale/...`).
  Read-only (`get/describe/logs/events/top`) is fine. Provide mutating
  commands for the owner to run.
- **Never** run mutating git commands. No commit/push.
- **Never** delete AWS resources. Provide the CLI command for the owner.
- DynamoDB writes from Python must convert floats to `Decimal(str(v))`. (Not
  directly relevant to this plan, but the tool handlers already do this — do
  not regress it.)
- Single k3s node is `sirsimpalot-g5-5000`; hostPath mounts resolve there.
- AWS region is `ca-central-1`. The DynamoDB tables are real/live; the tool
  env var `HEALTH_PROGRAM_PK=operator` is the live operator data. Do not point
  tests at `operator`.

---

## 2. Repository topology (where things live)

This is a two-repo setup inside one working tree:

- **Repo root `terraform/`** — the Kubernetes/infra stack, applied locally
  against the private k3s kubeconfig. Owns ALL k8s Fission CRs.
  - `terraform/k8s-fission-powerlifting.tf` — powerlifting Environment +
    Packages + Functions + HTTPTriggers (Problem A lives here).
  - `terraform/k8s-fission.tf` — OpenCode Environment + Function + Trigger
    (Problem B lives here).
  - `terraform/k8s-secrets.tf` — `pl_fission_secrets`, `if_agent_api_config`
    configmap (holds `OPENCODE_FISSION_URL`, `POWERLIFTING_LAMBDA_BASE_URL`).
  - `terraform/image.tf` — ECR repos + Packer build null_resources
    (`packer_build_opencode_runner`).
  - `terraform/variables-fission.tf` — fission vars.
- **`utils/powerlifting-app/`** — the powerlifting app repo.
  - `lambda/` — tool handlers (`<tool>/handler.py`, `<tool>/core.py`,
    `<tool>/resources.yaml`), `layers/` (vendored store modules), the Fission
    glue: `fission_entry.py`, `fission_layers.py`, `fission-deploy.py`.
  - `terraform/fission-build/*.zip` — the built per-tool archives
    (the literal that terraform base64-embeds; note these live UNDER the app
    repo terraform dir, and the repo-root `k8s-fission-powerlifting.tf`
    reads them via `local.pl_build_dir`).
  - `backend/src/utils/lambda.ts` — the HTTP client that POSTs to the router.
- **`utils/opencode-runner/`** — the Rust one-shot server (Problem B).
- **`docker/opencode-runner.pkr.hcl`** — Packer build for the runner image.

---

## 3. PART A — Fix powerlifting tool dependency installation

Goal: switch each tool Package from a **deployment archive** to a **source
archive + buildcmd**, so the Fission `python-builder` runs
`pip install -r requirements.txt` at build time. No image bundling.

### A.1 Add the Fission build script (Repo A)

The builder receives two env vars: `SRC_PKG` (the unzipped source dir) and
`DEPLOY_PKG` (the output dir that becomes the deploy archive). The standard
Fission Python build script installs requirements into the source tree, then
copies everything to the deploy dir. (This is the canonical pattern from the
Fission docs "Packaging source code".)

Create **`utils/powerlifting-app/lambda/fission_build.sh`** with EXACTLY:

```sh
#!/bin/sh
set -eu
pip3 install -r ${SRC_PKG}/requirements.txt -t ${SRC_PKG}
cp -r ${SRC_PKG}/. ${DEPLOY_PKG}/
```

Make it executable and keep it executable in git:

```bash
chmod +x utils/powerlifting-app/lambda/fission_build.sh
# (owner runs) git update-index --chmod=+x utils/powerlifting-app/lambda/fission_build.sh
```

> Why `cp -r ${SRC_PKG}/.`: copies the installed deps AND the handler code AND
> the vendored store modules AND `main.py` (the entry) into the deploy archive
> root. The entry module is still `main.main` (unchanged).

### A.2 Bake `build.sh` into every archive (Repo A)

Edit **`utils/powerlifting-app/lambda/fission-deploy.py`**, function
`_build_archive` (around lines 51-78). It already writes `main.py`,
`tool_id.txt`, the handler files, layer modules, and `requirements.txt`. Add
the build script to the zip root. Insert this near the top of the `with
zipfile.ZipFile(...)` block, right after `zf.write(ENTRY_FILE, ENTRY_ZIP_NAME)`:

```python
        # Fission source-archive build script: the python-builder runs this
        # (spec.buildcmd = "./build.sh") and it pip-installs requirements.txt
        # into the deploy archive. Lives at archive root as build.sh.
        zf.write(os.path.join(LAMBDA_ROOT, "fission_build.sh"), "build.sh")
```

Keep the existing `requirements.txt` write (lines ~75-77) — it is now actually
used by the builder instead of ignored.

> NOTE: `fission-deploy.py` also has a `generate_tf()` path that emits a
> divergent `fission-functions.tf`. The repo-root
> `k8s-fission-powerlifting.tf` is the source of truth and that generated file
> is NOT used. Do not call `generate_tf()`. Only the zip-building `main()`
> path matters. (If you want, delete the `generate_tf`/`LOOPS`/`HEADER`
> machinery in a later cleanup PR; not required for this fix.)

### A.3 Rebuild the archives (Repo A)

```bash
cd utils/powerlifting-app/lambda
python3 fission-deploy.py
# Expect: "built 96 archives in .../terraform/fission-build"
# Verify build.sh is now inside an archive:
unzip -l ../terraform/fission-build/health_get_program.zip | grep build.sh
```

### A.4 Convert Packages to source archive + buildcmd (Repo B)

Edit **`terraform/k8s-fission-powerlifting.tf`**, resource
`kubectl_manifest.pl_packages` (the `spec` block). Change `deployment` to
`source` and add `buildcmd`:

BEFORE:
```hcl
    spec = {
      environment = { name = "pl-fission-tools", namespace = kubernetes_namespace.if_portals.metadata[0].name }
      deployment  = { type = "literal", literal = filebase64("${local.pl_build_dir}/${each.key}.zip") }
    }
```
AFTER:
```hcl
    spec = {
      environment = { name = "pl-fission-tools", namespace = kubernetes_namespace.if_portals.metadata[0].name }
      source      = { type = "literal", literal = filebase64("${local.pl_build_dir}/${each.key}.zip") }
      buildcmd    = "./build.sh"
    }
```

### A.5 Revert the Environment + Function to stock Fission images (Repo B)

The live cluster drifted to a hand-built custom image
(`if-pl-fission-env:latest`) + manually patched AWS creds. We are going
Fission-native (NO image bundling), so the Environment must use stock images.
The `.tf` already declares stock images — we just must make sure the apply
overwrites the drift and add a bigger builder memory (pandas/scipy/chromadb
wheels are heavy to install).

Edit `kubectl_manifest.pl_fission_env` `spec` (around lines 65-75):

BEFORE:
```hcl
      runtime                = { image = "ghcr.io/fission/python-env" }
      builder                = { image = "ghcr.io/fission/python-builder" }
      terminationGracePeriod = 120
      resources = {
        requests = { cpu = "100m", memory = "128Mi" }
      }
```
AFTER:
```hcl
      runtime                = { image = "ghcr.io/fission/python-env" }
      builder                = { image = "ghcr.io/fission/python-builder" }
      terminationGracePeriod = 120
      resources = {
        requests = { cpu = "100m", memory = "512Mi" }
        limits   = { cpu = "1000m", memory = "2Gi" }
      }
```

> The `resources` here apply to the builder/runtime pods. 2Gi limit prevents
> OOM-kills while pip-installing pandas+numpy+scipy. If a build still OOMs,
> bump the limit to `3Gi`.

In `kubectl_manifest.pl_functions` podspec the container `image` is already
`ghcr.io/fission/python-env` (line ~166) — leave it. (Fission newdeploy
actually runs the Environment runtime image, not this podspec image, but keep
it consistent.)

### A.6 Give function pods AWS credentials via hostPath (Repo B)

The tool handlers call `boto3.resource("dynamodb", region_name=...)` (see
`utils/powerlifting-app/lambda/layers/pl-program/python/program_store.py`).
They need real AWS creds. The owner chose: **hostPath-mount the node's
`/root/.aws` into each function pod**, exactly like the opencode-runner and
every other pod does (`var.aws_credentials_host_path`, default `/root/.aws`).

This ALSO removes the terraform-drift footgun: today AWS creds were manually
`kubectl`-patched into the `pl-fission-secrets` Secret, and a `terraform
apply` would wipe them. With hostPath, creds come from the node and survive
applies, so `pl_fission_secrets` stays as terraform defines it
(`INTERNAL_API_TOKEN` + `OPENROUTER_API_KEY` only) — do NOT add AWS keys to
that Secret.

Edit `kubectl_manifest.pl_functions` podspec (around lines 150-184). Two
changes: add the env vars and add the volume + mount.

1. In the container `env = concat(...)` list, append a fixed entry so boto3
   reads the mounted credentials file and region:
```hcl
            env = concat(
              local.pl_common_env,
              [{ name = "IF_TOOL_NAME", value = each.key }],
              [
                { name = "AWS_SHARED_CREDENTIALS_FILE", value = "/root/.aws/credentials" },
                { name = "AWS_REGION", value = "ca-central-1" },
                { name = "AWS_DEFAULT_REGION", value = "ca-central-1" },
              ],
              each.value.class == "ai" ? local.pl_ai_env : [],
              try(each.value.s3_read, false) ? [{ name = "POWERLIFTING_S3_BUCKET", value = var.powerlifting_s3_bucket }] : [],
            )
```

2. Add a `volumeMounts` block to the container (it currently has none) and a
   `volumes` entry (currently `volumes = []`):
```hcl
            volumeMounts = [
              { name = "aws-credentials", mountPath = "/root/.aws", readOnly = true },
            ]
```
and
```hcl
        volumes = [
          {
            name     = "aws-credentials"
            hostPath = { path = var.aws_credentials_host_path, type = "Directory" }
          },
        ]
```

> `var.aws_credentials_host_path` already exists
> (`terraform/variables-resources.tf`, default `/root/.aws`). If that variable
> is not in scope in this file, it is a root-module variable so it is
> available; just reference it.
>
> Sanity check the node actually has creds there (read-only, safe):
> `kubectl debug` is not needed — the opencode-runner already mounts the same
> path successfully, so it is present.

### A.7 Reconcile scale profile (minor, optional but recommended)

`local.pl_scale` in `k8s-fission-powerlifting.tf` sets `warm = { min = 0 }`,
but `fission_layers.py SCALE_PROFILE` says warm `minReplicas = 1`. Pick one.
Recommendation: set warm `min = 1` in `pl_scale` so the hot read tools
(`health_get_program`, `health_get_session`, etc.) stay warm and the UI feels
instant. This is a 1-line change:
```hcl
    warm  = { min = 1, max = 2, cpu = 70, timeout = 60 }
```

### A.8 Apply Part A

Format/validate first (safe, non-mutating):
```bash
cd terraform
terraform fmt
terraform validate
terraform plan -target='kubectl_manifest.pl_fission_env' \
  -target='kubectl_manifest.pl_packages' \
  -target='kubectl_manifest.pl_functions'
```
Then present the targeted apply for the OWNER to run (needs approval):
```bash
terraform apply \
  -target='kubectl_manifest.pl_fission_env' \
  -target='kubectl_manifest.pl_packages' \
  -target='kubectl_manifest.pl_functions'
```

> Order matters: the Environment must update before packages rebuild. Applying
> all three targets together lets terraform order them via existing
> `depends_on`.

### A.9 Verify Part A

```bash
# 1. Packages should transition none -> building -> succeeded
kubectl get packages -n if-portals \
  -o custom-columns='NAME:.metadata.name,STATUS:.status.buildstatus' | head -40

# 2. If a build fails, read why:
kubectl get package pl-pkg-health-get-program -n if-portals \
  -o jsonpath='{.status.buildlog}{"\n"}'
# and the builder pod logs:
kubectl logs -n if-portals -l environmentName=pl-fission-tools --all-containers --tail=100

# 3. Smoke-test through the router (this is what the backend does).
#    Use a read tool with no required args. Run from inside the cluster:
kubectl run pltest --rm -i --restart=Never -n if-portals \
  --image=curlimages/curl --command -- \
  curl -s -m 120 -XPOST \
  http://router.fission.svc.cluster.local:80/health_get_program \
  -H 'Content-Type: application/json' -d '{}'
# Expect: HTTP 200 with a JSON body that is the program dict (or a
# structured "program not found" — NOT a connection error / empty hang).

# 4. Confirm the function pod reached the DB (no boto3/credentials error):
kubectl logs -n if-portals \
  -l functionName=pl-fn-health-get-program --all-containers --tail=50
```

Then check the live UI: port-forward the powerlifting frontend/backend and
load a page that triggers a tool call.
```bash
kubectl -n if-portals port-forward svc/powerlifting-app-backend 3005:3005
# hit the page that was returning nothing; watch backend logs for the
# router call succeeding (no "Lambda tool error"/timeout).
```

---

## 4. PART B — Re-model OpenCode runner as a newdeploy custom Environment

Goal: OpenCode works "the same way as the functions": a **newdeploy** Function
backed by a **custom Fission Environment image**. The only difference from the
powerlifting functions is the runtime is a lightweight Rust HTTP server (not
stock python-env). To be a valid Fission Environment runtime image, the Rust
server MUST implement Fission's environment HTTP protocol.

### B.0 The Fission Environment image protocol (authoritative)

This is the contract every Fission runtime image implements (taken from
Fission's reference environment servers). The runtime container:

- Binds **port `8888`** (NOT 8000). This is the port the Fission fetcher
  sidecar and router talk to.
- Implements these routes and STAYS RUNNING to serve repeated requests:
  - `GET /healthz` -> `200 OK`. Used as the readiness probe.
  - `POST /specialize` (v1). Body: none. Loads user code from the fixed path
    `/userfunc/user`. For us there is no user code to load — just mark ready.
  - `POST /v2/specialize`. Body is JSON `FunctionLoadRequest`:
    `{"filepath": "<abs path>", "functionName": "<entrypoint>", "url": "/"}`.
    Loads user code from `filepath`. For us: just mark ready.
  - Catch-all `/` (and any other path/method) -> dispatch to the "user
    function". For us, the "user function" IS the OpenCode job runner.
- Specialization happens ONCE per pod, before the pod serves traffic. After a
  successful specialize, the router forwards real requests to `/`.

> Key behavioral change vs today's one-shot server:
> - bind 8888 not 8000
> - add /healthz, /specialize, /v2/specialize
> - NEVER exit after a job; loop forever serving requests
> - the OpenCode job logic moves under the catch-all `/` handler
>
> The router strips the trigger relativeurl and forwards to the pod root, so
> the pod sees `/` (or the leftover path). Handle the job on ANY path that
> is not one of the protocol routes.

### B.1 Rewrite the Rust server

Replace **`utils/opencode-runner/src/main.rs`** with the structure below.
KEEP all existing job-execution helpers verbatim — `run_opencode`,
`stream_to_log_and_buf`, `list_artifacts`, `read_and_parse_job`,
`error_response`, `json_header`, the wire types (`OpencodeJobRequest`,
`OpencodeJobResponse`, `Artifact`), and the consts. ONLY the `main()` loop and
routing (`handle_request`) change. Here is the new top-level wiring; splice the
unchanged helpers back in below it:

```rust
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Read};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use tiny_http::{Header, Method, Response, Server, StatusCode};

// ... KEEP: RUNTIME_EXCLUDES, DEFAULT_* consts, STREAM_LIMIT_BYTES,
//           MAX_BODY_BYTES, all wire types, error_response(), json_header(),
//           read_and_parse_job(), run_opencode(), stream_to_log_and_buf(),
//           list_artifacts() — unchanged from the current file.

// Fission env protocol: bind 8888, stay alive, serve repeated requests.
const FISSION_ENV_PORT: u16 = 8888;

fn main() {
    // Fission talks to the runtime on 8888. We still allow PORT override for
    // local testing, but default to the Fission contract port.
    let port: u16 = std::env::var("PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(FISSION_ENV_PORT);
    let host = std::env::var("HOST").unwrap_or_else(|_| "0.0.0.0".to_string());
    let opencode_bin =
        std::env::var("OPENCODE_BIN").unwrap_or_else(|_| DEFAULT_OPENCODE_BIN.to_string());

    let bind_addr = format!("{}:{}", host, port);
    let server = Server::http(&bind_addr).unwrap_or_else(|e| {
        eprintln!("[opencode-runner] failed to bind {}: {}", bind_addr, e);
        std::process::exit(1);
    });
    eprintln!(
        "[opencode-runner] listening on {} (fission env protocol), opencode={}",
        bind_addr, opencode_bin
    );

    // `specialized` flips true after Fission calls /specialize or
    // /v2/specialize. There is no user code to load for this environment —
    // the "function" is the fixed OpenCode job runner — so specialize is just
    // a readiness handshake.
    let specialized = Arc::new(AtomicBool::new(false));

    // Serve forever. NEVER exit after a job (newdeploy keeps the pod warm and
    // the HPA scales it). Each request is handled synchronously; tiny_http
    // queues concurrent requests. OpenCode jobs are long, so we handle one at
    // a time per pod — set the Function MaxScale to fan out across pods.
    for req in server.incoming_requests() {
        handle_request(req, &opencode_bin, &specialized);
    }
}
```

The new `handle_request` (replaces the current one). Note it no longer returns
a bool and never signals exit:

```rust
#[derive(Debug, Deserialize)]
struct FunctionLoadRequest {
    #[serde(default)]
    filepath: String,
    #[serde(default)]
    #[serde(rename = "functionName")]
    function_name: String,
    #[serde(default)]
    url: String,
}

fn handle_request(
    mut req: tiny_http::Request,
    opencode_bin: &str,
    specialized: &Arc<AtomicBool>,
) {
    let method = req.method().clone();
    let url = req.url().to_string();
    // Path without query string.
    let path = url.split('?').next().unwrap_or("/").to_string();

    match (method.clone(), path.as_str()) {
        // Readiness probe — Fission polls this; must be cheap and always 200.
        (Method::Get, "/healthz") | (Method::Get, "/health") => {
            let _ = req.respond(Response::from_string("OK").with_status_code(StatusCode(200)));
        }
        // Fission v1 specialize: no body, fixed code path. We have no user
        // code to load — just flip ready and 200.
        (Method::Post, "/specialize") => {
            specialized.store(true, Ordering::SeqCst);
            eprintln!("[opencode-runner] specialized (v1)");
            let _ = req.respond(Response::from_string("").with_status_code(StatusCode(200)));
        }
        // Fission v2 specialize: JSON FunctionLoadRequest. We accept and
        // ignore the payload (no plugin to load); flip ready and 200.
        (Method::Post, "/v2/specialize") => {
            let mut body = String::new();
            let _ = req.as_reader().read_to_string(&mut body);
            // Parse best-effort just to log; ignore errors.
            if let Ok(load) = serde_json::from_str::<FunctionLoadRequest>(&body) {
                eprintln!(
                    "[opencode-runner] specialized (v2) filepath={} fn={} url={}",
                    load.filepath, load.function_name, load.url
                );
            } else {
                eprintln!("[opencode-runner] specialized (v2) [unparsed body]");
            }
            specialized.store(true, Ordering::SeqCst);
            let _ = req.respond(Response::from_string("").with_status_code(StatusCode(200)));
        }
        // Everything else is a real OpenCode job. The router forwards the
        // trigger to the pod root, and the IF agent posts to
        // /v1/opencode/execute; accept any non-protocol path here.
        (Method::Post, _) => {
            // If Fission has not specialized us yet, the pod is not ready;
            // 500 so the router retries against a ready pod.
            if !specialized.load(Ordering::SeqCst) {
                let _ = req.respond(
                    Response::from_string("not specialized")
                        .with_status_code(StatusCode(500)),
                );
                return;
            }
            let response = match read_and_parse_job(&mut req) {
                Ok(job) => run_opencode(&job, opencode_bin),
                Err(msg) => {
                    let body = serde_json::json!({"status": "error", "message": msg});
                    let json = serde_json::to_string(&body).unwrap_or_else(|_| "{}".into());
                    let _ = req.respond(
                        Response::from_string(json)
                            .with_header(json_header())
                            .with_status_code(StatusCode(400)),
                    );
                    return;
                }
            };
            let status = if response.status == "ok" { 200 } else { 500 };
            let json = serde_json::to_string(&response).unwrap_or_else(|_| "{}".into());
            let _ = req.respond(
                Response::from_string(json)
                    .with_header(json_header())
                    .with_status_code(StatusCode(status)),
            );
        }
        // GET/other on unknown path: 404 but stay alive.
        _ => {
            let body = serde_json::json!({"status": "error",
                "message": format!("not found: {} {}", method, path)});
            let json = serde_json::to_string(&body).unwrap_or_else(|_| "{}".into());
            let _ = req.respond(
                Response::from_string(json)
                    .with_header(json_header())
                    .with_status_code(StatusCode(404)),
            );
        }
    }
}
```

> Implementation notes for the junior:
> - `read_to_string` needs `use std::io::Read;` (already imported).
> - Remove the old `for req in ... { if handle_request(...) { break; } }`
>   pattern and the "opencode job completed, exiting" log — the server no
>   longer exits.
> - Keep `panic = "abort"` in Cargo.toml; a panic in one request aborts the
>   pod and Fission/newdeploy respawns it. Acceptable.
> - `serde_json` is already a dependency; `AtomicBool`/`Arc` are std.
> - Build locally to catch errors before image build:
>   `cd utils/opencode-runner && cargo build --release --locked`

### B.2 Update the Packer image to expose 8888

Edit **`docker/opencode-runner.pkr.hcl`**. In the `source "docker"` `changes`
block (around lines 51-56), change the exposed port from 8000 to 8888:

BEFORE:
```hcl
    "EXPOSE 8000",
```
AFTER:
```hcl
    "EXPOSE 8888",
```

The `CMD ["/app/opencode-runner"]` stays. No other Packer change is required
for correctness. (Optional later optimization: the image is ~591 MB and the
cold pull is ~42s; slimming it would further reduce first-request latency, but
it is not required once MinScale >= 1 keeps a pod warm.)

Rebuild + push the image (the Packer build pushes to ECR). This is a
null_resource keyed on a source hash; it triggers on the next apply, OR run
Packer directly:
```bash
cd docker
aws ecr get-login-password --region ca-central-1 | docker login --username AWS \
  --password-stdin <acct>.dkr.ecr.ca-central-1.amazonaws.com
packer init opencode-runner.pkr.hcl
packer build -var "image_repository=<acct>.dkr.ecr.ca-central-1.amazonaws.com/if-opencode-runner" \
  -var "image_tag=latest" opencode-runner.pkr.hcl
```
(The exact repo URL is `aws_ecr_repository.if_opencode_runner.repository_url`;
the terraform `packer_build_opencode_runner` null_resource in
`terraform/image.tf` runs this same command on apply when the source hash
changes.)

### B.3 Convert the Fission Environment to a newdeploy custom env (Repo B)

Edit **`terraform/k8s-fission.tf`**,
`kubectl_manifest.fission_environment_opencode_runner` (around lines 106-130).
Today it is `version: 1, poolsize: 0` and was paired with the container
executor. Make it a standard custom runtime Environment:

BEFORE:
```yaml
    spec:
      runtime:
        image: ${aws_ecr_repository.if_opencode_runner.repository_url}:latest
      version: 1
      keeparchive: false
      poolsize: 0
```
AFTER:
```yaml
    spec:
      runtime:
        image: ${aws_ecr_repository.if_opencode_runner.repository_url}:latest
      version: 3
      keeparchive: false
      # newdeploy does not pull from the poolmgr pool; poolsize 0 avoids
      # idle pool pods. The function below uses ExecutorType newdeploy.
      poolsize: 0
      imagepullsecret: ecr-registry
```

> Why version 3: enables the v2 specialize protocol + builder semantics the
> modern executor expects. Our image speaks /v2/specialize, so use 3.
> `imagepullsecret` lets Fission pull from the private ECR repo.

### B.4 Convert the Function from container -> newdeploy executor (Repo B)

Edit `kubectl_manifest.fission_function_opencode_job` (around lines 163-230).
Two categories of change: the InvokeStrategy and the container port/probe.

1. InvokeStrategy block (lines ~176-182):

BEFORE:
```yaml
      InvokeStrategy:
        ExecutionStrategy:
          ExecutorType: container
          MaxScale: ${var.opencode_runner_max_concurrent}
          MinScale: 0
          SpecializationTimeout: 120
        StrategyType: execution
```
AFTER:
```yaml
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
```

2. Container port: change `containerPort: 8000` to `8888` (line ~201) and the
   `PORT` env value `"8000"` to `"8888"` (lines ~206-207). The Rust server now
   defaults to 8888, but keep them aligned and explicit.

BEFORE:
```yaml
            ports:
              - containerPort: 8000
            securityContext:
              privileged: true
              runAsUser: 0
            env:
              - name: PORT
                value: "8000"
```
AFTER:
```yaml
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
```

> Leave the rest of the podspec (privileged, serviceAccountName
> opencode-runner, all the PVC mounts, aws-credentials hostPath, netrc,
> prompt/specialist/tool/models/skills/scripts hostPath mounts, resources,
> envFrom of if-agent-api-secrets/config/model-config) EXACTLY as-is. Those
> are correct and shared with the agent pod.
>
> Note: with newdeploy, Fission injects its fetcher sidecar and manages the
> Deployment + Service + HPA for you (same as the powerlifting functions).
> The stub Package `kubectl_manifest.fission_package_opencode_job` stays
> (empty literal archive) — Fission still requires a package ref; the runner
> binary is baked in the env image so nothing is fetched.

### B.5 App side — no change needed (verify only)

The IF agent already posts to the router:
- `app/src/flow/opencode.py` -> `run_opencode_via_fission(...)`
- `app/src/flow/opencode_fission.py` -> `POST {OPENCODE_FISSION_URL}/v1/opencode/execute`
- `OPENCODE_FISSION_URL = http://router.fission.svc.cluster.local:80`
  (set in `terraform/k8s-secrets.tf` configmap `if-agent-api-config`).

The HTTPTrigger relativeurl is `/v1/opencode/execute`
(`kubectl_manifest.fission_http_trigger_opencode_job`,
`var.fission_http_trigger_url`). The router forwards to the pod; our new
catch-all `POST` handler accepts any non-protocol path, so it handles both
`/v1/opencode/execute` (if forwarded verbatim) and `/` (if stripped). No app
or trigger change required.

### B.6 Apply Part B

```bash
cd terraform
terraform fmt
terraform validate
terraform plan \
  -target='null_resource.packer_build_opencode_runner' \
  -target='kubectl_manifest.fission_environment_opencode_runner' \
  -target='kubectl_manifest.fission_function_opencode_job'
```
Present for OWNER approval, then apply (this rebuilds+pushes the image and
updates the env+function):
```bash
terraform apply \
  -target='null_resource.packer_build_opencode_runner' \
  -target='kubectl_manifest.fission_environment_opencode_runner' \
  -target='kubectl_manifest.fission_function_opencode_job'
```

> If terraform does not detect the Rust source change for the Packer
> null_resource, it is keyed on `local.opencode_runner_hash`. Confirm that
> hash covers `utils/opencode-runner/src/**`. If a forced rebuild is needed,
> the owner can taint it:
> `terraform taint null_resource.packer_build_opencode_runner` then apply.

### B.7 Verify Part B

```bash
# 1. A warm pod should exist (MinScale 1) and be Ready on /healthz.
kubectl get deploy -n if-portals | grep opencode
kubectl get pods -n if-portals | grep opencode   # expect 1/1 Running (or 2/2 with fetcher)

# 2. The pod log should show the new banner + a specialize line.
kubectl logs -n if-portals -l functionName=opencode-job --all-containers --tail=40
# Expect: "listening on 0.0.0.0:8888 (fission env protocol)" and
#         "specialized (v2) ..."

# 3. Smoke test through the router (long timeout; OpenCode is slow).
#    Use a real session dir on the shared PVC and a valid allowlisted model.
kubectl run octest --rm -i --restart=Never -n if-portals \
  --image=curlimages/curl --command -- \
  curl -s -m 300 -XPOST \
  http://router.fission.svc.cluster.local:80/v1/opencode/execute \
  -H 'Content-Type: application/json' \
  -d '{"job_id":"smoke1","agent":"build","model":"deepseek/deepseek-v4-flash","prompt":"print hello","session_dir":"/app/src/data/conversations/smoke1","timeout_seconds":120}'
# Expect: JSON {"job_id":"smoke1","status":"ok"|"error", ...} — NOT a hang.

# 4. End-to-end: send a Discord/HTTP message that triggers an OpenCode run and
#    watch the agent log forward to fission and get a returncode.
kubectl logs -n if-portals deploy/if-agent-api --tail=80 | grep -i 'fission-opencode'
```

---

## 5. Rollback

### Part A rollback
- Revert the `pl_packages` spec to `deployment = { type = "literal", ... }`
  (drop `source`/`buildcmd`), revert `pl_fission_env` resources, and
  re-apply the same three targets. tfstate retains prior generations.
- If AWS creds were the only thing keeping old pods alive, the manual secret
  patch is no longer needed once hostPath is in place; do not re-add AWS keys
  to `pl_fission_secrets`.

### Part B rollback
- Revert `k8s-fission.tf` Environment (`version: 1`) and Function
  (`ExecutorType: container`, port 8000, no readinessProbe, MinScale 0), and
  `git checkout` the old `utils/opencode-runner/src/main.rs` and the Packer
  `EXPOSE 8000`. Rebuild image + re-apply the three targets.
- The app side never changed, so no app rollback is needed.

---

## 6. Troubleshooting cheat-sheet

| Symptom | Likely cause | Where to look |
|---|---|---|
| Package stuck `buildstatus: none` | still a deployment archive | A.4 — confirm `source` + `buildcmd` applied; `kubectl get package <p> -o yaml` |
| Package `buildstatus: failed` | pip install failed / OOM | `kubectl get package <p> -o jsonpath='{.status.buildlog}'`; bump builder mem (A.5) |
| Build log: `No such file: build.sh` | build.sh not in archive | A.2 — re-run `fission-deploy.py`, `unzip -l` to confirm |
| Tool pod 500 `Unable to locate credentials` | hostPath/env not applied | A.6 — check podspec env + volume; confirm `/root/.aws/credentials` exists on node |
| Tool pod `ResourceNotFoundException` | wrong table/region | confirm `pl_common_env` table names + `AWS_REGION` |
| OpenCode router hangs | pod not Ready / exited | B.7 — `kubectl get pods`, logs; ensure server does NOT exit after job |
| OpenCode pod CrashLoopBackOff | binds wrong port / panic | B.1/B.2 — confirm 8888 + readinessProbe path `/healthz` |
| OpenCode 500 `not specialized` | Fission did not call specialize | check env `version: 3`; check fetcher sidecar logs |
| `context canceled` in router log | upstream pod died mid-request | the function pod crashed — inspect that pod's logs |

Useful read-only commands:
```bash
kubectl get environments,packages,functions,httptriggers -n if-portals
kubectl logs -n fission deploy/executor --tail=100
kubectl logs -n fission deploy/buildermgr --tail=100
kubectl logs -n fission deploy/router --tail=100
kubectl get events -n if-portals --sort-by=.lastTimestamp | tail -30
```

---

## 7. Files you will touch

Repo A (powerlifting-app):
- `utils/powerlifting-app/lambda/fission_build.sh` (NEW)
- `utils/powerlifting-app/lambda/fission-deploy.py` (`_build_archive`: add build.sh)
- `utils/powerlifting-app/terraform/fission-build/*.zip` (REGENERATED by script)

Repo B (terraform root):
- `terraform/k8s-fission-powerlifting.tf` (packages source+buildcmd; env
  resources; function AWS env+volume; warm min scale)
- `terraform/k8s-fission.tf` (env version 3; function newdeploy + port 8888 +
  readinessProbe)

Runner + image:
- `utils/opencode-runner/src/main.rs` (protocol rewrite)
- `docker/opencode-runner.pkr.hcl` (EXPOSE 8888)

No changes to: `app/src/flow/opencode*.py`,
`terraform/k8s-secrets.tf` (pl_fission_secrets stays creds-free),
`backend/src/utils/lambda.ts`, the HTTPTriggers.

---

## 8. Suggested implementation order & PR boundaries

1. **PR 1 (Part A, app repo):** add `fission_build.sh`, edit
   `fission-deploy.py`, regenerate zips. Local-only; no cluster change.
2. **PR 2 (Part A, infra):** `k8s-fission-powerlifting.tf` package/env/function
   edits. `terraform fmt/validate/plan`. Owner targeted-applies. Verify A.9.
3. **PR 3 (Part B, runner):** rewrite `main.rs`, `EXPOSE 8888`,
   `cargo build --release --locked` locally green.
4. **PR 4 (Part B, infra):** `k8s-fission.tf` env+function edits. Owner applies
   (rebuilds image). Verify B.7.

Do Part A fully (through verification) before starting Part B — they are
independent, and isolating them makes debugging far easier.

## 9. Definition of done

- [ ] All `pl-pkg-*` packages show `buildstatus: succeeded`.
- [ ] `POST router/health_get_program` returns 200 JSON from inside cluster.
- [ ] Powerlifting UI pages that call tools render data (port-forward check).
- [ ] `opencode-job` has a warm Ready pod on `/healthz:8888`.
- [ ] `POST router/v1/opencode/execute` returns a job JSON (not a hang).
- [ ] An end-to-end agent message that uses OpenCode completes; agent log
      shows `[fission-opencode] ... returncode=0`.
- [ ] `terraform fmt` + `terraform validate` clean in `terraform/`.
- [ ] No AWS keys added to `pl_fission_secrets`; creds come from hostPath.
