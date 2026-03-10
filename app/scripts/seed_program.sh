#!/usr/bin/env bash
# Seeds the current peaking program into the if-health DynamoDB table.
#
# Creates:
#   - pk="operator#<your_pk>"  sk="program#current"  (pointer)
#   - pk="operator#<your_pk>"  sk="program#v001"      (full program)
#
# Requires: AWS CLI configured, Python 3 + boto3
# Usage:
#   ./seed_program.sh
#   IF_HEALTH_TABLE_NAME=my-table ./seed_program.sh
#   ./seed_program.sh --region us-west-2

set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-ca-central-1}"
TABLE="${IF_HEALTH_TABLE_NAME:-if-health}"
PK="${IF_OPERATOR_PK:-operator}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) REGION="$2"; shift 2 ;;
    --table)  TABLE="$2";  shift 2 ;;
    --pk)     PK="$2";     shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

echo "[seed_program] Table:  ${TABLE}"
echo "[seed_program] Region: ${REGION}"
echo "[seed_program] PK:     ${PK}"
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

def lb_to_kg(lb):
    return round(lb / 2.205, 1)

# ---------------------------------------------------------------------------
# Per-week data, parsed from spreadsheet.
#
# Exercise order per lift:
#   DEADLIFT : backout sets (straight sets) FIRST, then heavy top set
#   SQUAT    : backout heavy x2 FIRST, then main top set, then backout light x1
#   BENCH    : heavy top set first, then straight-set backouts (unchanged)
#
# W10 "break"     = 70% intensity — reduced volume. NOT a full rest week.
# W11 "comp week" = 50% intensity — opener simulation. NOT a full rest week.
# W1-W3 = completed as of 2026-03-08.
# ---------------------------------------------------------------------------
# Columns:
#   week_label, date,
#   sq_h, sq_h_reps,
#   sq_b2 (heavy backout ~90%), sq_b1 (light backout ~85%), sq_bo_reps,
#   dl_b (backout), dl_bo_reps, dl_h, dl_h_reps,
#   bp_h, bp_h_reps, bp_b, bp_bo_reps,
#   spoto_lb, pause_lb, shrugs_lb,
#   session_note, completed

WEEKS = [
  ("W1 (Warmup)","2026-02-15", 110,6,  101, 95, 6,   60,6, 103,6,   84,4,  73,6,   148,  166.5, 185,  "",                                                                          True),
  ("W2",         "2026-02-22", 125,4,  113,107, 6,  122,6, 143,6,   91,4,  78,6,   160,  180.0, 185,  "",                                                                          True),
  ("W3",         "2026-03-01", 143,4,  129,122, 6,  142,6, 166,5,   98,4,  83,6,   172,  193.5, 185,  "",                                                                          True),
  ("W4",         "2026-03-08", 150,4,  135,128, 6,  157,6, 184,4,  103,3,  87,5,   180,  202.5, 185,  "",                                                                          False),
  ("W5",         "2026-03-15", 162,3,  145,137, 5,  165,6, 193,4,  107,3,  91,5, 188.4, 211.95, 185,  "",                                                                          False),
  ("W6",         "2026-03-22", 171,3,  154,145, 5,  174,6, 205,3,  112,2,  95,4,   196,  220.5, 265,  "easy",                                                                      False),
  ("W7",         "2026-03-29", 180,2,  162,153, 4,  180,5, 211,2,  116,2,  99,4,   204,  229.5, 275.5,"struggled",                                                                 False),
  ("W8",         "2026-04-05", 184,2,  166,157, 4,  188,3, 220,1,  121,1, 103,3,   212,  238.5, 289.5,"failed",                                                                    False),
  ("W9",         "2026-04-12", 186,1,  168,159, 3,  196,3, 230,1,  125,1, 107,3,   220,  247.5, 303.5,"potential comp pr",                                                         False),
  ("W10",        "2026-04-19", 191,1,  172,162, 3,  203,3, 239,1,  130,1, 110,3,   228,  256.5, 317.5,"break — 70% intensity, reduced volume. NOT a full rest week.",               False),
  ("W11",        "2026-04-26", 200,1,  180,170, 3,  213,3, 250,1,  137,1, 116,3,   240,  270.0, 335.0,"comp week — 50% intensity, opener simulation. NOT a full rest week.",        False),
]

def build_sessions():
    sessions = []
    for row in WEEKS:
        (
            week_label, date,
            sq_h, sq_h_r, sq_b2, sq_b1, sq_bo_r,
            dl_b, dl_bo_r, dl_h, dl_h_r,
            bp_h, bp_h_r, bp_b, bp_bo_r,
            spo_lb, pau_lb, shr_lb,
            note, done
        ) = row

        exercises = [
            # DEADLIFT: backouts first (straight sets), then heavy
            {"name": "Deadlift (Backout)", "sets": 3, "reps": dl_bo_r, "kg": dl_b,
             "notes": "straight sets backout, done before heavy top set"},
            {"name": "Deadlift",           "sets": 1, "reps": dl_h_r,  "kg": dl_h,
             "notes": "heavy top set"},

            # SQUAT: heavy backout x2 -> main -> light backout x1
            {"name": "Squat (Backout Heavy)", "sets": 2, "reps": sq_bo_r, "kg": sq_b2,
             "notes": "~90% backout, 2 sets — done BEFORE main"},
            {"name": "Squat",                 "sets": 1, "reps": sq_h_r,  "kg": sq_h,
             "notes": "heavy top set"},
            {"name": "Squat (Backout Light)", "sets": 1, "reps": sq_bo_r, "kg": sq_b1,
             "notes": "~85% backout, 1 set — done AFTER main"},

            # BENCH: main -> backouts (unchanged)
            {"name": "Bench Press",           "sets": 1, "reps": bp_h_r,  "kg": bp_h,
             "notes": "heavy top set"},
            {"name": "Bench Press (Backout)", "sets": 3, "reps": bp_bo_r, "kg": bp_b,
             "notes": "straight sets backout"},

            # BENCH ACCESSORIES
            {"name": "Spoto Press",       "sets": 3, "reps": 5,  "kg": lb_to_kg(spo_lb),
             "notes": "2-3cm off chest, no touch"},
            {"name": "Pause Bench Press", "sets": 3, "reps": 5,  "kg": lb_to_kg(pau_lb),
             "notes": "2-second pause at chest"},
            {"name": "Shrugs",            "sets": 3, "reps": 10, "kg": lb_to_kg(shr_lb),
             "notes": "upper back / traps"},
        ]

        sessions.append({
            "week":           week_label,
            "date":           date,
            "day":            "Monday",
            "completed":      done,
            "session_rpe":    None,
            "body_weight_kg": None,
            "exercises":      exercises,
            "session_notes":  note,
        })
    return sessions


SUPPLEMENT_PHASES = [
    {
        "phase":      1,
        "phase_name": "Current Stack (now → ~W8, Apr 5)",
        "notes":      "Full general wellness + performance + hormonal stack.",
        "items": [
            {"name": "Creatine",          "dose": "10g/day"},
            {"name": "Vitamin D3+K2",     "dose": "standard dose"},
            {"name": "Boron",             "dose": "9mg/day"},
            {"name": "Tongkat Ali",       "dose": "900mg/day"},
            {"name": "BPC-157",           "dose": "2000mcg/day"},
            {"name": "Ashwagandha",       "dose": "2500mg/day"},
            {"name": "Zinc",              "dose": "200mg/day"},
            {"name": "Vitamin B Complex", "dose": "2 softgels/day (normal strength)"},
            {"name": "Maca",              "dose": "2800mg/day"},
            {"name": "Magnesium",         "dose": "600mg/day"},
        ],
    },
    {
        "phase":      2,
        "phase_name": "Performance Focus Transition (~W8, Apr 5-12)",
        "notes":      "Drop general wellness items. Shift entirely to performance and hormonal support. Exact protocol TBD.",
        "items":      [],
    },
    {
        "phase":      3,
        "phase_name": "Peak Stack — no water retention (last 4 weeks → comp)",
        "notes":      (
            "Drop creatine. Nothing that causes water retention. "
            "Salt and carb manipulation in final week for maximum water loss. "
            "Consider natural diuretics (dandelion root etc.) — TBD."
        ),
        "items": [
            {"name": "Tongkat Ali", "dose": "900mg/day",  "notes": "LH/testosterone support"},
            {"name": "Boron",       "dose": "9mg/day",    "notes": "free testosterone, joint support"},
            {"name": "Zinc",        "dose": "200mg/day",  "notes": "hormonal support"},
            {"name": "L-Theanine",  "dose": "TBD",        "notes": "focus, cortisol blunting"},
        ],
        "peak_week_protocol": {
            "strategy":        "salt and carb manipulation for water loss",
            "water_retention": "strict avoidance of anything that causes retention",
            "diuretics":       "natural diuretics TBD — decide closer to comp",
        },
    },
]

COMPETITIONS = [
    {
        "name":            "May 2026 Comp",
        "date":            "2026-05-30",
        "federation":      "CPU",
        "location":        "Local — ~20 min by Uber",
        "hotel_required":  False,
        "status":          "confirmed",
        "weight_class_kg": 74,
        "targets": {
            "squat_kg":    190,
            "bench_kg":    120,
            "deadlift_kg": 240,
            "total_kg":    550,
        },
        "notes": "Primary comp. Conservative targets (−10kg squat, −10kg bench vs program peak, rest from DL). No travel overhead.",
        "decision_date": None,
    },
    {
        "name":            "June 2026 Comp — Guelph (Optional)",
        "date":            "2026-06-12",
        "federation":      "CPU",
        "location":        "Guelph, ON — hotel required",
        "hotel_required":  True,
        "status":          "optional",
        "weight_class_kg": 83,
        "decision_date":   "2026-04-25",
        "targets": {
            "squat_kg":    200,
            "bench_kg":    130,
            "deadlift_kg": 250,
            "total_kg":    580,
        },
        "between_comp_plan": {
            "rest":          "1 full week no training post-May comp",
            "ramp_back":     "5 days at 50% intensity",
            "diet":          "Eating in surplus — intentionally targeting 83kg class for strength benefit",
            "weight_class":  "83kg (no cut, pigging out during break)",
            "inflammation":  "Keep break controlled enough that weight doesn't balloon uncontrollably",
        },
        "notes": (
            "Optional. Decision April 25 based on May comp result and weight situation. "
            "If 74kg weight cut looks bad before May → skip June, go all-out at May instead, then target Sept/Nov. "
            "Hotel + travel to Guelph adds overhead. Logic for going: surplus guarantees more strength at 83kg."
        ),
    },
]

program = {
    "meta": {
        "program_name":              "10-Week Peaking Program",
        "program_start":             "2026-02-15",
        "comp_date":                 "2026-05-30",
        "weight_class_kg":           74,
        "target_squat_kg":           190,
        "target_bench_kg":           120,
        "target_dl_kg":              240,
        "target_total_kg":           550,

        "current_body_weight_lb":    168,
        "current_body_weight_kg":    round(168 / 2.205, 1),
        "weight_class_confirm_by":   "2026-03-29",

        "last_comp": {
            "date":            "2025-09",
            "body_weight_lb":  170,
            "body_weight_kg":  round(170 / 2.205, 1),
            "weight_class_kg": 83,
            "results": {
                "squat_kg":    185,
                "bench_kg":    117.5,
                "deadlift_kg": 220,
                "total_kg":    522.5,
            },
            "past_comp_day_protocol": {
                "caffeine_total_mg": 800,
                "caffeine_sequence": [
                    {"timing": "before leaving for venue",   "dose_mg": 100, "notes": "half scoop — conservative start"},
                    {"timing": "after weigh-ins",            "dose_mg": 100, "notes": "half scoop — top up post cut"},
                    {"timing": "between squat and bench",    "dose_mg": 200, "notes": "full scoop"},
                    {"timing": "between bench and deadlift", "dose_mg": 200, "notes": "full scoop"},
                    {"timing": "after squat opener",         "dose_mg": 100, "notes": "half scoop"},
                    {"timing": "after bench opener",         "dose_mg": 100, "notes": "half scoop"},
                    {"timing": "after deadlift opener",      "dose_mg":   0, "notes": "skipped — last event, already fully ramped"},
                ],
                "l_theanine": "paired throughout to smooth edge",
                "carbs":      "energy gels between attempts for blood glucose",
                "outcome":    "performed well — total 522.5kg. Experienced significant panic attack post-comp, likely combination of caffeine load, adrenaline crash, and competition stress. Doable but not comfortable.",
                "notes":      "Do NOT use as a template for future comps without reassessment. 800mg under competition stress is high. State in 3 months unknown — revisit dose closer to May comp.",
            },
        },

        "federation":       "WRPF",
        "practicing_for":   "CPU",

        "training_notes": [
            "Bench responds better to volume — favour volume over intensity for bench development.",
            "Knees and back sensitive under squat and deadlift load — monitor, do not push through sharp pain.",
            "Weak points: hamstrings and glutes — historically insufficient direct work. Address in off-season programming.",
            "Squat order: heavy backout x2 (~90%) BEFORE main top set, light backout x1 (~85%) AFTER.",
            "Deadlift order: backout straight sets BEFORE the heavy top set.",
            "Bench order: heavy top set first, then straight-set backouts (unchanged).",
            "W10 (break) = 70% intensity, reduced volume — NOT a rest week.",
            "W11 (comp week) = 50% intensity, opener simulation — NOT a rest week.",
        ],

        "version_label": "1.0",
        "updated_at":    datetime.now(timezone.utc).isoformat(),
        "change_log":    [],
    },

    "phases": [
        {"name": "Warmup",          "start_week": 1,  "end_week": 1,  "intent": "Baseline — 60% loads, pattern groove"},
        {"name": "Base Build",      "start_week": 2,  "end_week": 5,  "intent": "Progressive overload, volume accumulation"},
        {"name": "Intensification", "start_week": 6,  "end_week": 8,  "intent": "Volume drops, loads climb toward near-max"},
        {"name": "Peak",            "start_week": 9,  "end_week": 9,  "intent": "Singles, confidence building, minimal fatigue"},
        {"name": "Break",           "start_week": 10, "end_week": 10, "intent": "70% intensity — active deload, NOT full rest"},
        {"name": "Comp Prep",       "start_week": 11, "end_week": 11, "intent": "50% intensity — opener simulation, final taper"},
    ],

    "competitions":      COMPETITIONS,
    "sessions":          build_sessions(),
    "diet_notes": [
        {
            "date":  "2026-03-08",
            "notes": (
                "Current: 168lb (~76.2kg). Target: 74kg class (≤163.1lb at weigh-in). "
                "Delta: ~5lb to drop. Must confirm on track by W7 (Mar 29 — 4 weeks from comp). "
                "Strategy: gradual diet deficit now, salt+carb manipulation in peak week. "
                "If cut looks unrealistic before May comp → move to June in 83kg class instead and go all-out."
            ),
        }
    ],
    "supplement_phases": SUPPLEMENT_PHASES,
    "supplements":       SUPPLEMENT_PHASES[0]["items"],  # current items for renderer.py compat
}

# ---------------------------------------------------------------------------
# Write to DynamoDB
# ---------------------------------------------------------------------------

now   = datetime.now(timezone.utc).isoformat()
table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE)

POINTER_SK = "program#current"
PROGRAM_SK = "program#v001"

print(f"[seed_program] Writing program item  → pk={PK!r}, sk={PROGRAM_SK!r}")
table.put_item(Item=to_d({"pk": PK, "sk": PROGRAM_SK, **program}))

print(f"[seed_program] Writing pointer item  → pk={PK!r}, sk={POINTER_SK!r}")
table.put_item(Item=to_d({"pk": PK, "sk": POINTER_SK, "version": 1, "ref_sk": PROGRAM_SK, "updated_at": now}))

m = program["meta"]
lc = m["last_comp"]["results"]
print("")
print("[seed_program] Done.")
print(f"  Weeks:      {len(program['sessions'])} sessions (W1–W11)")
print(f"  Baseline:   Squat {lc['squat_kg']}kg | DL {lc['deadlift_kg']}kg | Bench {lc['bench_kg']}kg  (Sep 2025 @ 83kg class)")
print(f"  May target: Squat {m['target_squat_kg']}kg | DL {m['target_dl_kg']}kg | Bench {m['target_bench_kg']}kg | Total {m['target_total_kg']}kg  (74kg)")
print(f"  Jun target: Squat 200kg | DL 250kg | Bench 130kg | Total 580kg  (83kg, optional — decide Apr 25)")
print(f"  Weight:     {m['current_body_weight_lb']}lb → confirm ≤74kg by {m['weight_class_confirm_by']}")
PYEOF
