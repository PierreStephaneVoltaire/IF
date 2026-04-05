#!/usr/bin/env bash
# Creates the two DynamoDB tables for IF Prototype A1.
# Requires: AWS CLI configured, appropriate IAM permissions.
# Usage: ./create_dynamo_tables.sh [--region us-east-1] [--billing PAY_PER_REQUEST|PROVISIONED]

set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-ca-central-1}"
BILLING="PAY_PER_REQUEST"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)   REGION="$2";  shift 2 ;;
    --billing)  BILLING="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# ─── Table 1: IF Core Store ────────────────────────────────────────────────────
# Purpose: webhooks, directives, activity logs, operator facts (existing design)
# PK: entity type + ID  (e.g. "webhook#abc123", "directive#Zero-One")
# SK: sub-type or timestamp (e.g. "record", "2024-01-01T00:00:00Z")

IF_CORE_TABLE="${IF_CORE_TABLE_NAME:-if-core}"

echo "[1/2] Creating table: ${IF_CORE_TABLE}"

aws dynamodb create-table \
  --region "${REGION}" \
  --table-name "${IF_CORE_TABLE}" \
  --attribute-definitions \
    AttributeName=pk,AttributeType=S \
    AttributeName=sk,AttributeType=S \
  --key-schema \
    AttributeName=pk,KeyType=HASH \
    AttributeName=sk,KeyType=RANGE \
  --billing-mode "${BILLING}" \
  --tags \
    Key=project,Value=if-prototype-a1 \
    Key=env,Value=prod \
  --no-cli-pager \
  --output json | jq -r '"  Status: " + .TableDescription.TableStatus'

echo "[1/2] Waiting for if-core-store to become ACTIVE..."
aws dynamodb wait table-exists --region "${REGION}" --table-name "${IF_CORE_TABLE}"
echo "[1/2] Done."

# ─── Table 2: IF Health Store ──────────────────────────────────────────────────
# Purpose: training programs, versioning, health context
# PK: "operator#<id>"   (e.g. "operator")
# SK: "program#current" | "program#v001" | "program#v002" ...
#
# program#current item:
#   { pk, sk, version: 3, ref_sk: "program#v003", updated_at: "ISO8601" }
#
# program#v{n} item:
#   { pk, sk, ...full program JSON... }
#
# TTL not enabled — programs are permanent versioned records.

IF_HEALTH_TABLE="${IF_HEALTH_TABLE_NAME:-if-health}"

echo "[2/2] Creating table: ${IF_HEALTH_TABLE}"

aws dynamodb create-table \
  --region "${REGION}" \
  --table-name "${IF_HEALTH_TABLE}" \
  --attribute-definitions \
    AttributeName=pk,AttributeType=S \
    AttributeName=sk,AttributeType=S \
  --key-schema \
    AttributeName=pk,KeyType=HASH \
    AttributeName=sk,KeyType=RANGE \
  --billing-mode "${BILLING}" \
  --tags \
    Key=project,Value=if-prototype-a1 \
    Key=env,Value=prod \
  --no-cli-pager \
  --output json | jq -r '"  Status: " + .TableDescription.TableStatus'

echo "[2/2] Waiting for if-health-store to become ACTIVE..."
aws dynamodb wait table-exists --region "${REGION}" --table-name "${IF_HEALTH_TABLE}"
echo "[2/2] Done."

# ─── Table 3: IF Finance ────────────────────────────────────────────────────
# Purpose: versioned financial profile storage
# PK: "user#<id>"        (e.g. "operator")
# SK: "finance#current"  → pointer { version, ref_sk, updated_at }
#     "finance#v001"...  → full versioned object
#
# finance#current item:
#   { pk, sk, version: 1, ref_sk: "finance#v001", updated_at: "ISO8601" }
#
# finance#v{n} item:
#   { pk, sk, ...full finance JSON... }
#
# TTL not enabled — finance records are permanent versioned.

IF_FINANCE_TABLE="${IF_FINANCE_TABLE_NAME:-if-finance}"

echo "[3/6] Creating table: ${IF_FINANCE_TABLE}"

aws dynamodb create-table \
  --region "${REGION}" \
  --table-name "${IF_FINANCE_TABLE}" \
  --attribute-definitions \
    AttributeName=pk,AttributeType=S \
    AttributeName=sk,AttributeType=S \
  --key-schema \
    AttributeName=pk,KeyType=HASH \
    AttributeName=sk,KeyType=RANGE \
  --billing-mode "${BILLING}" \
  --tags \
    Key=project,Value=if-prototype-a1 \
    Key=env,Value=prod \
  --no-cli-pager \
  --output json | jq -r '"  Status: " + .TableDescription.TableStatus'

echo "[3/6] Waiting for if-finance to become ACTIVE..."
aws dynamodb wait table-exists --region "${REGION}" --table-name "${IF_FINANCE_TABLE}"
echo "[3/6] Done."

# ─── Table 4: IF Diary Entries (TTL) ────────────────────────────────────────
# Purpose: write-only diary entries with 3-day TTL
# PK: "user#<id>"              (e.g. "operator")
# SK: "entry#<ISO8601>"        (e.g. "entry#2026-03-14T10:00:00Z")
#
# Item shape:
#   { pk, sk, content: "<raw rant>", created_at: "ISO8601", expires_at: <unix_ts> }
#
# TTL enabled on expires_at field — entries auto-delete after 3 days.
# Portal never reads content — only agent reads via tool for signal computation.

IF_DIARY_ENTRIES_TABLE="${IF_DIARY_ENTRIES_TABLE_NAME:-if-diary-entries}"

echo "[4/6] Creating table: ${IF_DIARY_ENTRIES_TABLE}"

aws dynamodb create-table \
  --region "${REGION}" \
  --table-name "${IF_DIARY_ENTRIES_TABLE}" \
  --attribute-definitions \
    AttributeName=pk,AttributeType=S \
    AttributeName=sk,AttributeType=S \
  --key-schema \
    AttributeName=pk,KeyType=HASH \
    AttributeName=sk,KeyType=RANGE \
  --billing-mode "${BILLING}" \
  --tags \
    Key=project,Value=if-prototype-a1 \
    Key=env,Value=prod \
  --no-cli-pager \
  --output json | jq -r '"  Status: " + .TableDescription.TableStatus'

echo "[4/6] Waiting for if-diary-entries to become ACTIVE..."
aws dynamodb wait table-exists --region "${REGION}" --table-name "${IF_DIARY_ENTRIES_TABLE}"

# Enable TTL on expires_at field
echo "[4/6] Enabling TTL on 'expires_at' field..."
aws dynamodb update-time-to-live \
  --region "${REGION}" \
  --table-name "${IF_DIARY_ENTRIES_TABLE}" \
  --time-to-live-specification "Enabled=true,AttributeName=expires_at" \
  --no-cli-pager

echo "[4/6] Done. TTL enabled on 'expires_at'."

# ─── Table 5: IF Diary Signals ──────────────────────────────────────────────
# Purpose: distilled signals from diary entries for charting and context injection
# PK: "user#<id>"                  (e.g. "operator")
# SK: "signal#<ISO8601>"           → historical record for charting
#     "signal#latest"              → pointer, always overwritten
#
# signal#latest item:
#   { pk, sk, score: 6.2, trend: "declining_slow", themes: [...],
#     life_load: "high", social_battery: "low", note: "...",
#     computed_at: "ISO8601", entry_count_used: 3 }
#
# Portal queries signal#* with begins_with for charting.
# Agent injects signal#latest into system prompt.

IF_DIARY_SIGNALS_TABLE="${IF_DIARY_SIGNALS_TABLE_NAME:-if-diary-signals}"

echo "[5/6] Creating table: ${IF_DIARY_SIGNALS_TABLE}"

aws dynamodb create-table \
  --region "${REGION}" \
  --table-name "${IF_DIARY_SIGNALS_TABLE}" \
  --attribute-definitions \
    AttributeName=pk,AttributeType=S \
    AttributeName=sk,AttributeType=S \
  --key-schema \
    AttributeName=pk,KeyType=HASH \
    AttributeName=sk,KeyType=RANGE \
  --billing-mode "${BILLING}" \
  --tags \
    Key=project,Value=if-prototype-a1 \
    Key=env,Value=prod \
  --no-cli-pager \
  --output json | jq -r '"  Status: " + .TableDescription.TableStatus'

echo "[5/6] Waiting for if-diary-signals to become ACTIVE..."
aws dynamodb wait table-exists --region "${REGION}" --table-name "${IF_DIARY_SIGNALS_TABLE}"
echo "[5/6] Done."

# ─── Table 6: IF Proposals ──────────────────────────────────────────────────
# Purpose: agent-proposed directives/tools requiring user approval
# PK: "user#<id>"                  (e.g. "operator")
# SK: "proposal#<ISO8601>"         (e.g. "proposal#2026-03-14T10:00:00Z")
#
# Item shape:
#   { pk, sk, type: "new_directive|rewrite_directive|deprecate_directive|new_tool|system_observation",
#     status: "pending|approved|rejected|implemented",
#     author: "agent|user", title: "", rationale: "", content: "",
#     target_id: "", implementation_plan: "",
#     created_at: "ISO8601", resolved_at: "ISO8601|null",
#     resolved_by: "user|null", rejection_reason: "null|string" }
#
# target_id: references existing directive sk for rewrite/deprecate
# implementation_plan: populated by background model after user approves

IF_PROPOSALS_TABLE="${IF_PROPOSALS_TABLE_NAME:-if-proposals}"

echo "[6/6] Creating table: ${IF_PROPOSALS_TABLE}"

aws dynamodb create-table \
  --region "${REGION}" \
  --table-name "${IF_PROPOSALS_TABLE}" \
  --attribute-definitions \
    AttributeName=pk,AttributeType=S \
    AttributeName=sk,AttributeType=S \
  --key-schema \
    AttributeName=pk,KeyType=HASH \
    AttributeName=sk,KeyType=RANGE \
  --billing-mode "${BILLING}" \
  --tags \
    Key=project,Value=if-prototype-a1 \
    Key=env,Value=prod \
  --no-cli-pager \
  --output json | jq -r '"  Status: " + .TableDescription.TableStatus'

echo "[6/6] Waiting for if-proposals to become ACTIVE..."
aws dynamodb wait table-exists --region "${REGION}" --table-name "${IF_PROPOSALS_TABLE}"
echo "[6/6] Done."

echo ""
echo "All 6 tables are ACTIVE."
echo "  Core store:       ${IF_CORE_TABLE}"
echo "  Health store:     ${IF_HEALTH_TABLE}"
echo "  Finance store:    ${IF_FINANCE_TABLE}"
echo "  Diary entries:    ${IF_DIARY_ENTRIES_TABLE}"
echo "  Diary signals:    ${IF_DIARY_SIGNALS_TABLE}"
echo "  Proposals:        ${IF_PROPOSALS_TABLE}"
echo ""
echo "Add to your .env:"
echo "  IF_CORE_TABLE_NAME=${IF_CORE_TABLE}"
echo "  IF_HEALTH_TABLE_NAME=${IF_HEALTH_TABLE}"
echo "  IF_FINANCE_TABLE_NAME=${IF_FINANCE_TABLE}"
echo "  IF_DIARY_ENTRIES_TABLE_NAME=${IF_DIARY_ENTRIES_TABLE}"
echo "  IF_DIARY_SIGNALS_TABLE_NAME=${IF_DIARY_SIGNALS_TABLE}"
echo "  IF_PROPOSALS_TABLE_NAME=${IF_PROPOSALS_TABLE}"
echo "  IF_MODELS_TABLE_NAME=${IF_MODELS_TABLE}"
