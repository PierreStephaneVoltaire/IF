#!/usr/bin/env bash
# reset-fission-packages.sh — nuke all powerlifting Fission Packages so the
# buildermgr rebuilds them from a clean slate.
#
# WHY
# ----
# The Packages were first created as `deployment` archives, so the Fission
# buildermgr stamped `.status.buildstatus = "none"` ("deployable, skip build").
# They were then switched to `source` + `buildcmd` archives so pip would install
# requirements. A `kubectl apply` only patches `.spec`; it never clears
# `.status`, so the status stayed stuck at "none" and nothing ever built — the
# fetcher crashes (`Get "": unsupported protocol scheme ""`) and every function
# pod CrashLoops ("no response").
#
# Deleting the Package CRs wipes `.status` entirely. The next `terraform apply`
# recreates them with an empty status, the buildermgr stamps "pending", and the
# python-builder runs `pip install -r requirements.txt` (build.sh). Run this,
# then run your targeted terraform apply.
#
# Also: there is a single shared python-builder pod. If you let the buildermgr
# fire all ~96 builds at once they collide on a shared temp zip path
# (`error archiving zip file: file already exists`) and fail. So this script
# deletes everything, then waits for in-flight builds to drain, then recreates
# them ONE AT A TIME so the builder only ever has one build in flight.
#
# USAGE
# -----
#   bash scripts/reset-fission-packages.sh
#
# After it finishes, run your terraform apply (targeted or full) to recreate the
# Package CRs. Or pass --recreate to have this script recreate them via
# kubectl apply right after deleting (uses the same zips terraform uses).
set -euo pipefail

PORTALS_NS="${PORTALS_NS:-if-portals}"
PL_BUILD_DIR="${PL_BUILD_DIR:-$(cd "$(dirname "$0")/.." && pwd)/utils/powerlifting-app/terraform/fission-build}"
RECREATE="${RECREATE:-0}"
REDEPLOY_FUNCTIONS="${REDEPLOY_FUNCTIONS:-0}"
for arg in "$@"; do
  case "$arg" in
    --recreate) RECREATE=1 ;;
    --redeploy-functions) REDEPLOY_FUNCTIONS=1 ;;
  esac
done

log() { printf '[reset-fission] %s\n' "$*" >&2; }

# If only --redeploy-functions was requested, skip the package reset entirely.
if [ "$REDEPLOY_FUNCTIONS" = "1" ] && [ "$RECREATE" = "0" ]; then
  log "skipping package reset (--redeploy-functions only)."
else

# ─── 1. Delete every pl-pkg-* Package ───────────────────────────────────────
log "deleting all pl-pkg-* packages in ${PORTALS_NS}..."
deleted=0
for p in $(kubectl get packages -n "$PORTALS_NS" -o name 2>/dev/null | grep '/pl-pkg-' || true); do
  if kubectl delete "$p" -n "$PORTALS_NS" --wait=false >/dev/null 2>&1; then
    deleted=$((deleted + 1))
  fi
done
log "deleted ${deleted} packages."

# ─── 2. Wait for them to actually be gone (finalizers can lag) ───────────────
log "waiting for deletions to finalize..."
for i in $(seq 1 60); do
  remaining=$(kubectl get packages -n "$PORTALS_NS" -o name 2>/dev/null | grep -c '/pl-pkg-' || true)
  [ "$remaining" -eq 0 ] && break
  log "  still ${remaining} terminating..."
  sleep 5
done

if [ "$RECREATE" = "1" ]; then
  # ─── 2b. Drain any in-flight builds before recreating ───────────────────
  # Deleting a Package CR does NOT cancel a build already running on the
  # shared python-builder pod. If a stray build is still in flight when we
  # recreate the first package, the two collide on the builder's shared temp
  # zip path (`error archiving zip file: file already exists`) and fail. So
  # wait until the builder is fully idle first.
  log "draining any in-flight builds before recreating..."
  for i in $(seq 1 60); do
    running=$(kubectl get packages -n "$PORTALS_NS" -o custom-columns='STATUS:.status.buildstatus' --no-headers 2>/dev/null | grep -c 'running' || true)
    pending=$(kubectl get packages -n "$PORTALS_NS" -o custom-columns='STATUS:.status.buildstatus' --no-headers 2>/dev/null | grep -c 'pending' || true)
    if [ "$running" -eq 0 ] && [ "$pending" -eq 0 ]; then
      log "builder idle."
      break
    fi
    log "  waiting for ${running} running / ${pending} pending builds to finish..."
    sleep 10
  done

  # ─── 2c. Restart the builder pod to wipe its polluted /packages emptyDir ─
  # The Fission python-builder stores build artifacts in an emptyDir at
  # /packages. After many failed builds (e.g. from a flood of concurrent
  # clears), that dir fills with hundreds of stale zip files. New builds then
  # fail with `error archiving zip file: file already exists` even when the
  # builder is otherwise idle — the stale files confuse the upload step.
  # Deleting the builder pod forces the Deployment to recreate it with a
  # fresh emptyDir, clearing the pollution. This is safe: Fission tolerates a
  # builder pod restart (it just rebuilds on the next package event).
  builder_deploy="$(kubectl get deploy -n "$PORTALS_NS" -o name 2>/dev/null | grep 'pl-fission-tools' | grep -v poolmgr | head -1 || true)"
  if [ -n "$builder_deploy" ]; then
    log "restarting builder (${builder_deploy}) to wipe stale /packages artifacts..."
    # Delete every pod the builder Deployment owns. The Fission builder pod
    # uses the label `envName` (not `environmentName`); match the Deployment's
    # pod-template-hash to target exactly the builder pods.
    pod_hash="$(kubectl get "$builder_deploy" -n "$PORTALS_NS" \
      -o jsonpath='{.spec.template.metadata.labels.pod-template-hash}' 2>/dev/null || true)"
    if [ -n "$pod_hash" ]; then
      kubectl delete pods -n "$PORTALS_NS" -l "pod-template-hash=${pod_hash}" --ignore-not-found=true >/dev/null 2>&1 || true
    else
      # Fallback: delete by envName label.
      kubectl delete pods -n "$PORTALS_NS" -l "envName=pl-fission-tools" --ignore-not-found=true >/dev/null 2>&1 || true
    fi
    # Wait for the new builder pod to be Ready.
    log "waiting for builder pod to come back..."
    for i in $(seq 1 60); do
      ready=$(kubectl get pods -n "$PORTALS_NS" -l "envName=pl-fission-tools" \
        -o jsonpath='{.items[0].status.containerStatuses[0].ready}' 2>/dev/null || true)
      [ "$ready" = "true" ] && { log "builder pod ready."; break; }
      sleep 5
    done
  fi

  # ─── 3a. Recreate from the built zips (one at a time, waiting for each) ──
  if [ ! -d "$PL_BUILD_DIR" ]; then
    log "ERROR: build dir not found: ${PL_BUILD_DIR}"
    log "       run: cd utils/powerlifting-app/lambda && python3 fission-deploy.py"
    exit 1
  fi
  zips=( "$PL_BUILD_DIR"/*.zip )
  total="${#zips[@]}"
  log "recreating ${total} packages from ${PL_BUILD_DIR} (one at a time)..."
  n=0
  tmpyaml="$(mktemp)"
  trap 'rm -f "$tmpyaml"' EXIT
  for z in "${zips[@]}"; do
    tool="$(basename "$z" .zip)"
    name="pl-pkg-${tool//_/-}"
    n=$((n + 1))
    log "  [${n}/${total}] ${name}"
    # Write the YAML to a temp file by streaming: print the YAML header, then
    # append the base64 directly from the file (no bash variable). Storing 85MB
    # of base64 in a bash var and expanding it in a heredoc is fragile (it can
    # hit arg-list limits and kill the script). Streaming avoids that.
    {
      printf 'apiVersion: fission.io/v1\n'
      printf 'kind: Package\n'
      printf 'metadata:\n  name: %s\n  namespace: %s\n' "$name" "$PORTALS_NS"
      printf 'spec:\n  environment:\n    name: pl-fission-tools\n    namespace: %s\n' "$PORTALS_NS"
      printf '  source:\n    type: literal\n    literal: ' "$PORTALS_NS"
      base64 -w0 "$z"
      printf '\n  buildcmd: ./build.sh\n'
    } > "$tmpyaml"
    if ! kubectl apply -f "$tmpyaml" -n "$PORTALS_NS" >/dev/null 2>&1; then
      log "    -> apply FAILED (kubectl apply error); skipping"
      continue
    fi
    # Wait for this one build to finish before starting the next, so the
    # single shared builder pod never has two builds colliding.
    for i in $(seq 1 60); do
      st="$(kubectl get package "$name" -n "$PORTALS_NS" \
        -o jsonpath='{.status.buildstatus}' 2>/dev/null || true)"
      case "$st" in
        succeeded|failed) break ;;
        "") sleep 3 ;;
        *) sleep 5 ;;
      esac
    done
    st="$(kubectl get package "$name" -n "$PORTALS_NS" \
      -o jsonpath='{.status.buildstatus}' 2>/dev/null || true)"
    log "    -> ${st:-unknown}"
  done
  rm -f "$tmpyaml"
  trap - EXIT
  log "done. final status:"
  kubectl get packages -n "$PORTALS_NS" -o custom-columns='NAME:.metadata.name,STATUS:.status.buildstatus' --no-headers 2>/dev/null | grep '^pl-pkg-' | sort
else
  # ─── 3b. Just report; terraform will recreate on apply ──────────────────
  log "all pl-pkg-* packages deleted."
  log "now run: terraform apply -target='kubectl_manifest.pl_packages'"
fi

fi # end of package-reset block (skipped when --redeploy-functions only)

# ─── 4. Redeploy function pods (optional, --redeploy-functions) ────────────
# Fission's newdeploy executor does NOT reconcile an existing Deployment when
# the Function CR's podspec changes (e.g. adding an AWS creds hostPath volume).
# The live Deployment stays at revision 1 with the old podspec forever. To
# pick up the new podspec you must delete the Deployment so Fission recreates
# it from the current Function CR. This is safe: Fission immediately recreates
# the Deployment and new pods roll out.
if [ "$REDEPLOY_FUNCTIONS" = "1" ]; then
  log "deleting all pl-fn-* function Deployments so Fission recreates them with the updated podspec..."
  fn_deps=$(kubectl get deploy -n "$PORTALS_NS" -o name 2>/dev/null | grep 'pl-fn-' || true)
  fn_count=0
  for d in $fn_deps; do
    kubectl delete "$d" -n "$PORTALS_NS" --wait=false >/dev/null 2>&1 && fn_count=$((fn_count + 1)) || true
  done
  log "deleted ${fn_count} function Deployments."
  log "waiting for Fission to recreate them..."
  # Fission's executor reconciles quickly; give it a few seconds then verify.
  sleep 10
  current=$(kubectl get deploy -n "$PORTALS_NS" -o name 2>/dev/null | grep -c 'pl-fn-' || echo 0)
  log "done. current function Deployments: ${current}"
  log "(expect ${fn_count} — if fewer, Fission is still recreating; check again in 30s)"
fi
