#!/usr/bin/env bash
# Claude Code PreToolUse guard.
# Protects the live IF agent API (deployment if-agent-api in if-portals) from
# being nuked — if it goes down, no incoming Discord/HTTP messages get picked up.
# Portal backends/frontends may be mutated freely.
# stdin = tool-input JSON; exit 2 + stderr => blocked.
set -euo pipefail
input="$(cat)"

# --- terraform: always-protected (app is live) ---
if printf '%s' "$input" | grep -qE 'terraform[[:space:]]+destroy'; then
  echo "BLOCKED: 'terraform destroy' is forbidden (app is live). Give the operator the command to run manually." >&2
  exit 2
fi
if printf '%s' "$input" | grep -qE 'terraform[[:space:]]+apply' && ! printf '%s' "$input" | grep -q -- '-target'; then
  echo "BLOCKED: non-targeted 'terraform apply' is forbidden (app is live). Only 'terraform apply -target=...' is allowed, with explicit operator approval. Otherwise give the operator the command." >&2
  exit 2
fi

# --- kubectl: node-level commands always blocked on this single-node cluster ---
if printf '%s' "$input" | grep -qE 'kubectl[[:space:]]+(cordon|drain)'; then
  echo "BLOCKED: 'kubectl cordon/drain' on a single-node cluster takes down everything, including the live IF agent API. Give the operator the command." >&2
  exit 2
fi

# --- kubectl: destructive verbs, scoped to the IF agent API ---
if printf '%s' "$input" | grep -qE 'kubectl[[:space:]]+(delete|apply|patch|edit|replace|scale|rollout)'; then
  if printf '%s' "$input" | grep -qi 'if-agent'; then
    echo "BLOCKED: destructive kubectl targeting the IF agent API (if-agent-*) is forbidden — nuking it stops all incoming message pickup. Portal backends/frontends may be mutated freely. Give the operator the command." >&2
    exit 2
  fi
  if printf '%s' "$input" | grep -qi 'app=if-agent-api'; then
    echo "BLOCKED: destructive kubectl targeting pods labelled app=if-agent-api is forbidden — that is the IF agent API. Give the operator the command." >&2
    exit 2
  fi
  if printf '%s' "$input" | grep -qi 'if-portals' && printf '%s' "$input" | grep -qE '([[:space:]]all[[:space:]"])|--all'; then
    echo "BLOCKED: broad 'all'/'--all' kubectl in the if-portals namespace would catch the live IF agent API. Target a specific non-agent resource, or give the operator the command." >&2
    exit 2
  fi
fi

exit 0
