#!/usr/bin/env bash
# Seeds example proposals into the if-proposals DynamoDB table.
#
# Creates 3 example proposals so the proposals portal renders non-empty on first launch.
#
# Requires: AWS CLI configured, Python 3 + boto3
# Usage:
#   ./seed_proposals.sh
#   IF_PROPOSALS_TABLE_NAME=my-table ./seed_proposals.sh
#   ./seed_proposals.sh --region us-west-2

set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-ca-central-1}"
TABLE="${IF_PROPOSALS_TABLE_NAME:-if-proposals}"
PK="${IF_USER_PK:-operator}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) REGION="$2"; shift 2 ;;
    --table)  TABLE="$2";  shift 2 ;;
    --pk)     PK="$2";     shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

echo "[seed_proposals] Table:  ${TABLE}"
echo "[seed_proposals] Region: ${REGION}"
echo "[seed_proposals] PK:     ${PK}"
echo ""

python3 /dev/stdin <<PYEOF
import boto3
from datetime import datetime, timezone, timedelta
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
# Example proposals - one of each type for portal rendering
# ---------------------------------------------------------------------------

now = datetime.now(timezone.utc)

# Create timestamps spaced by 1 hour to show ordering
ts1 = (now - timedelta(hours=2)).isoformat()
ts2 = (now - timedelta(hours=1)).isoformat()
ts3 = now.isoformat()

EXAMPLE_PROPOSALS = [
    {
        "pk": PK,
        "sk": f"proposal#{ts1}",
        "type": "new_directive",
        "status": "pending",
        "author": "agent",
        "title": "CONTEXT_WINDOW_DISCIPLINE",
        "rationale": "Agent observed user frequently re-provides context that was already shared in earlier messages, suggesting the agent may not be retaining or referencing prior conversation context effectively.",
        "content": "When responding to follow-up questions, explicitly reference and build upon previously shared context before introducing new information. Acknowledge what the user has already told you to demonstrate continuity.",
        "target_id": None,
        "implementation_plan": None,
        "created_at": ts1,
        "resolved_at": None,
        "resolved_by": None,
        "rejection_reason": None,
    },
    {
        "pk": PK,
        "sk": f"proposal#{ts2}",
        "type": "system_observation",
        "status": "pending",
        "author": "agent",
        "title": "Evening Productivity Pattern Detected",
        "rationale": "Analysis of interaction timestamps and query complexity suggests the user is most productive and engaged with complex tasks during evening hours (20:00-23:00 local time).",
        "content": "Consider scheduling complex brainstorming sessions, code reviews, and strategic planning discussions for evening hours. Lighter tasks (quick questions, formatting, simple lookups) may be better suited for daytime.",
        "target_id": None,
        "implementation_plan": None,
        "created_at": ts2,
        "resolved_at": None,
        "resolved_by": None,
        "rejection_reason": None,
    },
    {
        "pk": PK,
        "sk": f"proposal#{ts3}",
        "type": "new_tool",
        "status": "pending",
        "author": "agent",
        "title": "Calendar Integration Tool",
        "rationale": "User frequently mentions meetings, deadlines, and scheduling conflicts. A calendar integration tool would enable proactive scheduling assistance and deadline tracking.",
        "content": "Proposed tool: calendar_integration\n\nCapabilities:\n- Query upcoming events and meetings\n- Check availability for scheduling\n- Set reminders for important deadlines\n- Track recurring commitments\n\nWould integrate with Google Calendar API or similar service.",
        "target_id": None,
        "implementation_plan": None,
        "created_at": ts3,
        "resolved_at": None,
        "resolved_by": None,
        "rejection_reason": None,
    },
]

# ---------------------------------------------------------------------------
# Write to DynamoDB
# ---------------------------------------------------------------------------

table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE)

for proposal in EXAMPLE_PROPOSALS:
    sk = proposal["sk"]
    print(f"[seed_proposals] Writing proposal → pk={PK!r}, sk={sk!r}")
    # Convert None to string "null" for DynamoDB compatibility
    item = {}
    for k, v in proposal.items():
        if v is None:
            item[k] = "null"
        else:
            item[k] = v
    table.put_item(Item=to_d(item))

print("")
print("[seed_proposals] Done.")
print(f"  Seeded {len(EXAMPLE_PROPOSALS)} example proposals:")
print("    1. new_directive: CONTEXT_WINDOW_DISCIPLINE")
print("    2. system_observation: Evening Productivity Pattern")
print("    3. new_tool: Calendar Integration Tool")
print("")
print("  Review and resolve via proposals portal or agent tools.")
PYEOF
