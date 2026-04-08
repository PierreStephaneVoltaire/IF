#!/usr/bin/env bash
# PreToolUse hook for Bash tool — blocks kubectl mutating commands.
# kubectl get/describe/logs/events are allowed. Everything else requires
# the operator to run it manually.

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || true)

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Allow read-only kubectl commands
if echo "$COMMAND" | grep -qE 'kubectl\s+(get|describe|logs|events|top|api-resources|api-versions|version|config|auth\s+can-i)\b'; then
  exit 0
fi

# Block all other kubectl commands (delete, apply, patch, edit, replace, scale, rollout, cordon, drain, etc.)
if echo "$COMMAND" | grep -qE 'kubectl\b'; then
  echo '{"decision":"block","reason":"kubectl mutating command blocked. Provide the command to the operator instead of running it. get/describe/logs/events/top are allowed."}'
  exit 0
fi

exit 0
