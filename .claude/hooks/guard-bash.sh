#!/usr/bin/env bash
# PreToolUse hook for Bash tool — blocks dangerous commands.
# Input: JSON on stdin with tool_input.command
# Output: JSON decision to stdout

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || true)

if [ -z "$COMMAND" ]; then
  exit 0
fi

# ─── Terraform apply/destroy ─────────────────────────────────────────
# Block ALL terraform apply/destroy. Targeted (-target=) requires
# AskUserQuestion approval first, then user overrides this hook.
if echo "$COMMAND" | grep -qE 'terraform\s+(apply|destroy)\b'; then
  echo '{"decision":"block","reason":"terraform apply/destroy blocked. Use AskUserQuestion to get explicit operator approval first. Targeted -target= runs are the only exception, and only after approval."}'
  exit 0
fi

# ─── AWS resource deletion ───────────────────────────────────────────
# Never delete AWS resources. Give the operator the command instead.
if echo "$COMMAND" | grep -qE 'aws\s+\S+\s+(delete|remove|terminate|detach|deregister|disassociate)\b'; then
  echo '{"decision":"block","reason":"AWS resource deletion blocked. Provide the command to the operator instead of running it."}'
  exit 0
fi

# ─── Git mutating commands ──────────────────────────────────────────
# No git write privileges. Provide the command for the operator instead.
if echo "$COMMAND" | grep -qE 'git\s+(commit|push|merge|rebase|reset\s+--hard|checkout\s+-b|branch\s+-[dD]|tag|stash\s+drop|reflog\s+delete)\b'; then
  echo '{"decision":"block","reason":"Git write command blocked. No write privileges. Provide the command to the operator to run manually."}'
  exit 0
fi

exit 0
