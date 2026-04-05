#!/usr/bin/env bash
# Seeds the initial finance profile into the if-finance DynamoDB table.
#
# Creates:
#   - pk="user#<your_pk>"  sk="finance#current"  (pointer)
#   - pk="user#<your_pk>"  sk="finance#v001"      (full profile)
#
# Requires: AWS CLI configured, Python 3 + boto3
# Usage:
#   ./seed_finance.sh
#   IF_FINANCE_TABLE_NAME=my-table ./seed_finance.sh
#   ./seed_finance.sh --region us-west-2

set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-ca-central-1}"
TABLE="${IF_FINANCE_TABLE_NAME:-if-finance}"
PK="${IF_USER_PK:-operator}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) REGION="$2"; shift 2 ;;
    --table)  TABLE="$2";  shift 2 ;;
    --pk)     PK="$2";     shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

echo "[seed_finance] Table:  ${TABLE}"
echo "[seed_finance] Region: ${REGION}"
echo "[seed_finance] PK:     ${PK}"
echo ""

python3 /dev/stdin <<PYEOF
import boto3
from datetime import datetime, timezone
from decimal import Decimal
import json

def to_d(obj):
    """Recursively convert floats to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: to_d(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_d(i) for i in obj]
    return obj

TABLE  = "${TABLE}"
REGION = "${REGION}"
PK     = "${PK}"

# ---------------------------------------------------------------------------
# Finance profile structure (placeholder values - to be filled in by user)
# ---------------------------------------------------------------------------

finance_profile = {
    "meta": {
        "currency": "CAD",
        "province": "ON",
        "last_reviewed": datetime.now(timezone.utc).isoformat(),
    },

    "profile": {
        "age": 0,
        "employment": {
            "status": "full_time",  # full_time | part_time | self_employed | unemployed | student | retired
            "role": "",
            "company": "",
            "tenure_years": 0,
            "gross_annual_income": 0,
            "trajectory": "",  # growing | stable | declining | uncertain
            "near_term_change_risk": "low",  # low | medium | high
        },
        "net_monthly_income": 0,
        "secondary_income": [],  # [{ source, monthly_amount, stability }]
        "tax_bracket_federal": 0.0,  # marginal rate
        "tax_bracket_provincial": 0.0,
    },

    "goals": {
        "short_term": [  # < 1 year
            # { "goal": "", "target_amount": 0, "deadline": "YYYY-MM-DD", "priority": "high|medium|low" }
        ],
        "medium_term": [  # 1-5 years
            # { "goal": "", "target_amount": 0, "deadline": "YYYY-MM-DD", "priority": "high|medium|low" }
        ],
        "long_term": [  # 5+ years
            # { "goal": "", "target_amount": 0, "deadline": "YYYY-MM-DD", "priority": "high|medium|low" }
        ],
    },

    "risk_profile": {
        "tolerance": "moderate",  # conservative | moderate | aggressive
        "time_horizon_years": 0,
        "investment_philosophy": "",
        "max_drawdown_comfort_pct": 0,
        "notes": "",
    },

    "net_worth_snapshot": {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "total_assets": 0,
        "total_liabilities": 0,
        "net_worth": 0,
    },

    "accounts": {
        "chequing": [
            # { "name": "", "institution": "", "balance": 0, "is_primary": true }
        ],
        "savings": [
            # { "name": "", "institution": "", "balance": 0, "purpose": "" }
        ],
        "credit_cards": [
            # { "name": "", "institution": "", "limit": 0, "balance": 0, "interest_rate": 0 }
        ],
        "lines_of_credit": [
            # { "name": "", "institution": "", "limit": 0, "balance": 0, "interest_rate": 0 }
        ],
        "loans": [
            # { "name": "", "type": "mortgage|car|student|personal", "original_amount": 0,
            #   "balance": 0, "interest_rate": 0, "monthly_payment": 0, "term_months": 0 }
        ],
    },

    "investment_accounts": [
        # { "name": "", "type": "rrsp|tfsa|non_registered|resp", "institution": "",
        #   "balance": 0, "contribution_room_used": 0, "asset_allocation": { "equities": 0, "fixed_income": 0, "cash": 0 } }
    ],

    "watchlist": [
        # { "symbol": "", "name": "", "notes": "" }
    ],

    "monthly_cashflow": {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "net_monthly_income": 0,
        "fixed_expenses": [
            # { "name": "", "amount": 0, "due_day": 1, "category": "" }
        ],
        "debt_payments": [
            # { "name": "", "amount": 0, "type": "" }
        ],
        "savings_and_investments": [
            # { "name": "", "amount": 0, "type": "" }
        ],
        "variable_expense_budget": [
            # { "category": "", "budget": 0 }
        ],
        "total_fixed": 0,
        "total_debt_payments": 0,
        "total_savings_investments": 0,
        "total_variable_budget": 0,
        "total_outflow": 0,
        "monthly_surplus": 0,
    },

    "insurance": [
        # { "type": "life|disability|critical_illness|health|home|auto",
        #   "provider": "", "coverage_amount": 0, "monthly_premium": 0, "expiry": "" }
    ],

    "tax": {
        "last_year_return_filed": False,
        "last_refund_or_owing": 0,
        "ytd_rrsp_contributions": 0,
        "unused_rrsp_room": 0,
        "tfsa_room_used_this_year": 0,
        "capital_gains_ytd": 0,
        "notes": "",
    },

    "agent_context": {
        "known_biases": [],  # e.g. "overly conservative", "paralysis by analysis"
        "recurring_questions": [],  # topics user frequently asks about
        "notes": "",
    },

    "version_label": "1.0",
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "change_log": [],
}

# ---------------------------------------------------------------------------
# Write to DynamoDB
# ---------------------------------------------------------------------------

now   = datetime.now(timezone.utc).isoformat()
table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE)

POINTER_SK = "finance#current"
PROFILE_SK = "finance#v001"

print(f"[seed_finance] Writing profile item  → pk={PK!r}, sk={PROFILE_SK!r}")
table.put_item(Item=to_d({"pk": PK, "sk": PROFILE_SK, **finance_profile}))

print(f"[seed_finance] Writing pointer item  → pk={PK!r}, sk={POINTER_SK!r}")
table.put_item(Item=to_d({
    "pk": PK,
    "sk": POINTER_SK,
    "version": 1,
    "ref_sk": PROFILE_SK,
    "updated_at": now
}))

print("")
print("[seed_finance] Done.")
print("  Finance profile seeded with placeholder values.")
print("  Update via portal or agent tools with actual financial data.")
PYEOF
