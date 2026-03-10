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
# PK: "operator#<id>"   (e.g. "operator#pierre")
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

echo ""
echo "Both tables are ACTIVE."
echo "  Core store:   ${IF_CORE_TABLE}"
echo "  Health store: ${IF_HEALTH_TABLE}"
echo ""
echo "Add to your .env:"
echo "  IF_CORE_TABLE_NAME=${IF_CORE_TABLE}"
echo "  IF_HEALTH_TABLE_NAME=${IF_HEALTH_TABLE}"
