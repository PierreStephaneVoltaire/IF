#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../../.." && pwd)
app="$root/utils/powerlifting-app"
expected=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["source_hashes"]["package_manifest"])' "$root/deploy/rewrite/powerlifting-backlog/domain-candidates.json")
actual=$(cd "$app" && {
  printf '%s\n' package-lock.json package.json tsconfig.json backend/package.json backend/tsconfig.json frontend/package.json frontend/tsconfig.json packages/types/package.json packages/types/tsconfig.json
} | LC_ALL=C sort | while IFS= read -r file; do sha256sum "$file"; done | LC_ALL=C sort | sha256sum | cut -d' ' -f1)
[[ "$actual" == "$expected" ]] || { printf 'package manifest hash mismatch: expected %s, got %s\n' "$expected" "$actual" >&2; exit 1; }
printf '%s\n' "$actual"
