---

# Excel Import Feature — Full Design Document

**Project:** Powerlifting Peaking Portal
**Feature:** Excel / CSV Program Import
**Date:** 2026-04-14
**Status:** Pre-implementation

---

## 1. Overview

This feature adds structured import of external training programs into the portal, covering two distinct import types — reusable **Templates** (RPE / percentage based, no dates) and concrete **Session Imports** (actual training logs with dates and absolute weights). It also introduces the **Template Library**, **Glossary auto-import**, **Block → Template conversion**, and **Archive / Unarchive** as supporting primitives required by the import flows.

Everything described here is available both in the portal UI and as agent tools callable from Discord via the `health_write` specialist.

---

## 2. Concepts and Terminology

| Term | Definition |
|---|---|
| **Template** | A date-free, reusable program structure. Sets are expressed as `% of max` or `@ RPE`. Stored under `template#vNNN` SK namespace. |
| **Session Import** | A concrete training log with real dates and absolute kg values. Merges into the current program version. |
| **Concretization** | The act of applying a Template to a block — resolving `% / RPE` to actual kg using current e1RM, and mapping week/day structure to calendar dates. |
| **Max Resolution Gate** | A hard block on Template application when a required exercise has no e1RM or estimate available. |
| **Pending Import** | A staged, unconfirmed import record. One allowed per import type at a time. Must be applied or rejected before a new import of the same type can be submitted. |
| **Glossary** | The canonical exercise registry (`glossary#v1`). Source of truth for exercise identity, fatigue profiles, and e1RM estimates used in backfill. |
| **e1RM Estimate** | A per-exercise estimated one-rep max stored on the glossary entry. Used when no logged e1RM exists. May be manually set or AI backfilled. |
| **load\_source** | Discriminator on every planned set: `absolute`, `rpe`, `percentage`, `unresolvable`. |

---

## 3. Data Model

### 3.1 New SK Namespaces

#### `template#vNNN`

```json
{
  "pk": "operator",
  "sk": "template#v001",
  "meta": {
    "name": "Sheiko No.37",
    "source_filename": "sheiko_37.xlsx",
    "source_file_hash": "sha256:abc123...",
    "description": "Classic Sheiko 4-day peaking block",
    "estimated_weeks": 10,
    "days_per_week": 4,
    "created_at": "2026-04-14T19:42:08+00:00",
    "updated_at": "2026-04-14T19:42:08+00:00",
    "archived": false,
    "derived_from_template_sk": null,
    "derived_from_program_sk": null,
    "ai_evaluation": {
      "evaluated_at": "2026-04-14T19:42:08+00:00",
      "stance": "monitor",
      "strengths": [],
      "weaknesses": [],
      "suggestions": [],
      "context_snapshot": {
        "dots_score": 342,
        "weeks_to_comp": 12,
        "current_maxes": { "squat": 185, "bench": 115, "deadlift": 220 }
      }
    }
  },
  "phases": [
    {
      "name": "Accumulation",
      "week_start": 1,
      "week_end": 4,
      "target_rpe_min": 6,
      "target_rpe_max": 8,
      "intent": "Volume build"
    }
  ],
  "sessions": [
    {
      "id": "tpl_uuid_001",
      "week_number": 1,
      "day_of_week": "Monday",
      "day_index": 1,
      "label": "W1D1",
      "exercises": [
        {
          "name": "Squat",
          "glossary_id": "squat",
          "sets": 5,
          "reps": 3,
          "load_type": "rpe",
          "load_value": null,
          "rpe_target": 8.0,
          "notes": ""
        },
        {
          "name": "Romanian Deadlift",
          "glossary_id": "romanian_deadlift",
          "sets": 3,
          "reps": 6,
          "load_type": "percentage",
          "load_value": 0.70,
          "rpe_target": null,
          "notes": ""
        },
        {
          "name": "Tempo Squat",
          "glossary_id": null,
          "sets": 3,
          "reps": 4,
          "load_type": "unresolvable",
          "load_value": null,
          "rpe_target": null,
          "notes": "No load info in source file"
        }
      ]
    }
  ],
  "glossary_resolution": {
    "resolved": ["Squat", "Bench Press", "Deadlift", "Romanian Deadlift"],
    "unresolved": ["Tempo Squat"],
    "auto_added": ["Romanian Deadlift"],
    "resolution_status": "partial"
  },
  "required_maxes": ["squat", "bench", "deadlift", "romanian_deadlift"],
  "_rules": [
    "No dates on template sessions — week_number and day_of_week only",
    "load_type: rpe | percentage | absolute | unresolvable",
    "absolute load_type means the source file had hard kg numbers — flag for user review",
    "glossary_id null = unresolved exercise, blocks concretization",
    "ai_evaluation regenerated on-demand or when template is edited"
  ]
}
```

#### `template#current_list`

```json
{
  "pk": "operator",
  "sk": "template#current_list",
  "templates": [
    {
      "sk": "template#v001",
      "name": "Sheiko No.37",
      "source_filename": "sheiko_37.xlsx",
      "source_file_hash": "sha256:abc123...",
      "estimated_weeks": 10,
      "days_per_week": 4,
      "archived": false,
      "created_at": "2026-04-14T19:42:08+00:00"
    }
  ],
  "updated_at": "2026-04-14T19:42:08+00:00"
}
```

#### `import#pending#{uuid}`

```json
{
  "pk": "operator",
  "sk": "import#pending#a1b2c3d4",
  "import_id": "a1b2c3d4",
  "import_type": "session_import",
  "status": "awaiting_review",
  "source_filename": "march_log.xlsx",
  "source_file_hash": "sha256:def456...",
  "uploaded_at": "2026-04-14T19:42:08+00:00",
  "expires_at": "2026-04-21T19:42:08+00:00",
  "ttl": 1745353328,
  "ai_parse_result": {},
  "merge_strategy": null,
  "applied_at": null,
  "rejected_at": null,
  "rejection_reason": null,
  "_rules": [
    "DynamoDB TTL auto-purges after 7 days if not applied or rejected",
    "One pending record per import_type at a time — enforced at upload",
    "Hash check on upload prevents re-submitting same file while pending exists"
  ]
}
```

---

### 3.2 Modifications to Existing Schemas

#### `planned_exercises` — add `load_source` and `rpe_target`

Every entry in `planned_exercises` on a live session gains two new optional fields:

```json
{
  "name": "Squat",
  "sets": 5,
  "reps": 3,
  "kg": null,
  "rpe_target": 8.0,
  "load_source": "rpe"
}
```

| `load_source` value | `kg` | `rpe_target` | Meaning |
|---|---|---|---|
| `"absolute"` | present | optional | Hard number from program |
| `"rpe"` | `null` | present | Resolve at runtime from e1RM |
| `"percentage"` | computed at concretization | optional | Was a `%` in template, kg filled at apply time |
| `"unresolvable"` | `null` | `null` | No load info — exclude from projections |

> **Note:** `"percentage"` sets have their `kg` computed and stored at template-apply time using the e1RM at that moment. They are functionally identical to `"absolute"` after concretization — the distinction is retained for lineage only.

#### `glossary` exercises — add `e1rm_estimate`

```json
{
  "id": "romanian_deadlift",
  "name": "Romanian Deadlift",
  "e1rm_estimate": {
    "value_kg": 145.0,
    "method": "ai_backfill",
    "basis": "0.78 × deadlift e1RM (220kg) — hip hinge, similar leverages",
    "confidence": "low",
    "set_at": "2026-04-14T19:42:08+00:00",
    "manually_overridden": false
  }
}
```

`method` values: `"manual"`, `"ai_backfill"`, `"logged"` (derived from actual training history).
`confidence` values: `"high"` (logged), `"medium"` (manual entry), `"low"` (AI backfill).

#### `program#meta` — add `archived` and `template_lineage`

```json
{
  "meta": {
    "archived": false,
    "archived_at": null,
    "template_lineage": {
      "applied_template_sk": "template#v001",
      "applied_at": "2026-04-14T19:42:08+00:00",
      "week_start_day": "Saturday",
      "start_date": "2026-04-19"
    }
  }
}
```

---

## 4. Import Classification Logic

The AI parser receives the raw file content and must first classify it before extracting structure. Classification is deterministic where possible — the AI is a fallback for ambiguous files.

### 4.1 Deterministic Pre-classification (pre-AI)

Run these checks server-side before the AI call to reduce token cost:

```python
def preclassify_file(rows: list[dict]) -> str | None:
    has_dates = any(looks_like_date(cell) for row in rows for cell in row.values())
    has_absolute_kg = any(
        looks_like_kg(cell) and not looks_like_percentage(cell)
        for row in rows for cell in row.values()
    )
    has_rpe_col = any("rpe" in str(k).lower() for row in rows for k in row.keys())
    has_pct_col = any(
        looks_like_percentage(cell)
        for row in rows for cell in row.values()
    )

    if has_dates and has_absolute_kg and not has_pct_col:
        return "session_import"
    if not has_dates and (has_pct_col or has_rpe_col):
        return "template"
    return None  # ambiguous — send to AI
```

### 4.2 AI Classification Prompt

Only reached when pre-classification returns `None`.

```
You are classifying a training program spreadsheet.

CLASSIFICATION RULES:
- "template": program has no real calendar dates; loads are expressed as
  percentages of max (e.g. "75%", "0.75") or RPE targets (e.g. "@8", "RPE 8").
  Week references are relative (Week 1, W1, Day 1) not calendar dates.
- "session_import": program contains real calendar dates and absolute kg values.
  It is a training log of what was or will be done on specific days.
- "ambiguous": cannot determine confidently from the data alone.

Return JSON only:
{
  "classification": "template | session_import | ambiguous",
  "confidence": 0.0-1.0,
  "reasoning": "one sentence",
  "ambiguity_reason": "if ambiguous, what is unclear"
}
```

If `ambiguous` is returned, surface both interpretations to the user with the AI's reasoning and ask them to confirm before proceeding.

---

## 5. Template Import Flow

```
Upload
  │
  ├─ Hash check → duplicate? → show existing, block re-import
  │
  ├─ Pending check → template import pending? → show pending, block new upload
  │
  ├─ Pre-classify → AI classify if needed
  │
  ├─ AI Parse (see §8.1)
  │   ├─ Extract phases, week structure, sessions, exercises
  │   ├─ Detect load_type per exercise
  │   └─ Flag absolute weights as warnings
  │
  ├─ Glossary Resolution (see §8.4)
  │   ├─ Fuzzy pre-match (rapidfuzz, threshold 0.85)
  │   ├─ AI resolution for non-matches
  │   ├─ Queue unresolved for auto-add
  │   └─ Output: resolved[], auto_add_candidates[], unresolved[]
  │
  ├─ Stage as import#pending
  │   └─ status: "awaiting_review", TTL: 7 days
  │
  ├─ User Review (UI)
  │   ├─ Week × day grid preview
  │   ├─ Glossary resolution status per exercise
  │   ├─ Manual name mapping overrides
  │   ├─ Absolute weight warnings
  │   └─ Apply / Reject
  │
  └─ On Apply
      ├─ Increment template version counter
      ├─ Write template#vNNN
      ├─ Update template#current_list
      ├─ Auto-add glossary entries (minimal, fatigue_profile_source: "pending")
      ├─ Mark import#pending as applied
      └─ Async: AI fatigue estimation for auto-added exercises
```

---

## 6. Session Import Flow

```
Upload
  │
  ├─ Hash check → Pending check → Classify (same as template)
  │
  ├─ AI Parse (see §8.1)
  │   ├─ Extract dates, exercises, sets, reps, kg, RPE
  │   ├─ Map to session schema
  │   └─ Derive week labels from date ranges
  │
  ├─ Glossary Resolution (same as template flow)
  │
  ├─ Conflict Detection
  │   └─ For each imported session date against current program:
  │       ├─ completed session → PROTECT (hard lock, never overwrite)
  │       ├─ planned session exists → CONFLICT (user resolves)
  │       └─ new date → SAFE
  │
  ├─ Stage as import#pending
  │   ├─ Include full diff: new / conflict / protected
  │   └─ TTL: 7 days
  │
  ├─ User Review (UI)
  │   ├─ Per-session conflict resolution:
  │   │   ├─ Keep existing planned
  │   │   ├─ Replace with import
  │   │   └─ Merge (append imported as variant)
  │   ├─ Protected completed sessions shown greyed, locked
  │   └─ Overall merge strategy:
  │       ├─ Selective (per-session choices above)
  │       ├─ Replace non-completed only
  │       └─ Append only (new dates, skip all conflicts)
  │
  └─ On Apply
      ├─ Write new program#vNNN (never mutate in place)
      ├─ Apply conflict resolutions
      ├─ Preserve all completed sessions untouched
      ├─ Update program#current ref_sk
      ├─ Mark import#pending as applied
      └─ Async: recalculate analytics for affected weeks
```

---

## 7. Template → Block Application Flow

```
User selects template → clicks "Apply to Block"
  │
  ├─ Choose target:
  │   ├─ New block (archive current → new program version)
  │   ├─ Append to current block
  │   └─ Replace non-completed sessions in current block
  │
  ├─ Set start date + week_start_day (Sat / Mon / Sun)
  │
  ├─ Max Resolution Gate
  │   ├─ Collect required_maxes from template
  │   ├─ Check: current_maxes (SBD always present post-onboarding)
  │   ├─ Check: glossary.e1rm_estimate for accessories
  │   └─ MISSING → hard block, modal:
  │       "These exercises need a max estimate:
  │        [Romanian Deadlift] [Tempo Squat]
  │        ▸ Enter manually   ▸ AI estimate from current maxes"
  │
  ├─ AI Weight Backfill (if gate triggered, see §8.2)
  │   └─ Stores result in glossary.e1rm_estimate, confidence: "low"
  │
  ├─ Concretize Sessions
  │   ├─ Map week_number + day_of_week → calendar dates
  │   │   using start_date and week_start_day
  │   ├─ For each exercise:
  │   │   ├─ load_type = "rpe"
  │   │   │   → kg: null, rpe_target: value, load_source: "rpe"
  │   │   ├─ load_type = "percentage"
  │   │   │   → kg: round_to_2_5(e1rm × load_value), load_source: "percentage"
  │   │   ├─ load_type = "absolute"
  │   │   │   → kg: value, load_source: "absolute"
  │   │   └─ load_type = "unresolvable"
  │   │       → kg: null, load_source: "unresolvable"
  │   └─ status: "planned" on all sessions
  │
  ├─ Preview concretized calendar to user
  │   └─ User confirms
  │
  └─ On Confirm
      ├─ Write new program#vNNN
      ├─ Store template_lineage on meta
      └─ Update program#current
```

---

## 8. AI Calls

### 8.1 File Parse

**Trigger:** Every import upload after classification
**Model tier:** Standard
**Tool:** `import_parse_file`

**Input:**

```json
{
  "file_content": "<xlsx extracted to structured text via SheetJS/openpyxl>",
  "file_name": "sheiko_37.xlsx",
  "classification": "template",
  "athlete_context": {
    "current_maxes": { "squat": 185, "bench": 115, "deadlift": 220 },
    "current_program_weeks": 10
  }
}
```

**System prompt:**

```
You are a powerlifting program parser. Extract structured training data
from the provided spreadsheet content.

OUTPUT RULES:
- Return valid JSON only. No prose, no markdown fences.
- All load values: if percentage, express as decimal (0.75 not 75%).
- load_type must be one of: "rpe" | "percentage" | "absolute" | "unresolvable"
- If a set has kg values that are clearly absolute weights (not percentages),
  use load_type "absolute" — this is a warning condition for templates.
- Do not invent exercises, phases, or sessions not present in the source.
- If a field is genuinely absent, use null — do not guess.
- Weeks must be relative integers (1, 2, 3...) for templates.
  For session imports, use ISO date strings (YYYY-MM-DD).

WARNINGS to include in output:
- absolute_weights_in_template: list of exercises with hard kg in a template file
- missing_load_info: exercises with neither kg, %, nor RPE
- ambiguous_structure: anything structurally unclear

Return schema:
{
  "phases": [...],
  "sessions": [...],
  "warnings": [
    { "type": "string", "exercises": [], "message": "string" }
  ],
  "parse_notes": "string — brief summary of what was detected"
}
```

---

### 8.2 Weight Backfill for Accessories

**Trigger:** Max Resolution Gate finds missing e1RM, user selects AI estimate
**Model tier:** Air
**Tool:** `import_backfill_maxes`

**Input:**

```json
{
  "missing_exercises": ["Romanian Deadlift", "Pause Squat", "Tempo Bench"],
  "current_maxes": { "squat": 185, "bench": 115, "deadlift": 220 },
  "lift_profiles": [
    { "lift": "squat", "style_notes": "High bar, beltless", "primary_muscle": "Quads" }
  ],
  "body_metrics": { "height_cm": 175.5, "leg_length_cm": 100.0 }
}
```

**System prompt:**

```
You are estimating training maxes for powerlifting accessory exercises
based on an athlete's competition lift maxes.

RULES:
- Use anatomical and biomechanical reasoning — relate each accessory to its
  closest primary lift by movement pattern and muscle overlap.
- Express estimates as a ratio of the relevant primary lift e1RM.
- Be conservative. Underestimating is safer than overestimating.
- Confidence:
    "medium" — well-established ratio (e.g. RDL to deadlift)
    "low"    — speculative or unusual exercise

Return JSON only:
{
  "estimates": [
    {
      "exercise": "Romanian Deadlift",
      "e1rm_kg": 145.0,
      "ratio": 0.78,
      "primary_lift_used": "deadlift",
      "basis": "Hip hinge, similar leverages, typically 75-80% of deadlift",
      "confidence": "medium"
    }
  ]
}
```

---

### 8.3 Template Evaluation

**Trigger:** User requests evaluation on a saved template
**Model tier:** Heavy
**Tool:** `import_evaluate_template`

**Input:**

```json
{
  "template": {
    "meta": { "estimated_weeks": 10, "days_per_week": 4 },
    "phases": [],
    "sessions": []
  },
  "athlete_context": {
    "current_maxes": { "squat": 185, "bench": 115, "deadlift": 220 },
    "dots_score": 342,
    "lift_profiles": [],
    "competitions": [],
    "weeks_to_comp": 14,
    "acwr_current": 1.1,
    "fatigue_index": 0.28,
    "readiness_score": 81,
    "diet_notes": [],
    "supplements": []
  }
}
```

**System prompt:**

```
You are evaluating a powerlifting training template against an athlete's
current profile and competition timeline.

RULES:
- Be specific and data-cited. Reference weeks, exercises, phases by name.
- stance values: "continue" | "monitor" | "adjust" | "critical"
  "continue"  — template is well-matched to athlete profile and timeline
  "monitor"   — viable but has elements to watch
  "adjust"    — specific changes recommended before applying
  "critical"  — template is poorly matched or potentially harmful
- strengths and weaknesses: minimum 2 each if data supports it
- suggestions: each must cite the specific data point motivating it
- projected_readiness_at_comp: integer 0-100, use readiness formula logic
- Do not invent data not present in the input.
- If athlete_context fields are null or absent, note the missing context
  and adjust confidence accordingly. Do not refuse to evaluate.

PLANNED SESSION INTERPRETATION:
- Sets with load_type "rpe" and no kg: treat as intensity-regulated.
  Estimate relative intensity as RPE 10 ≈ 100%, RPE 9 ≈ 96%, RPE 8 ≈ 92%,
  RPE 7 ≈ 88% of current e1RM for qualitative volume assessment.
- Sets with load_type "percentage": use load_value × e1RM for intensity.
- Sets with load_type "unresolvable": exclude from volume assessment,
  note as incomplete data.
- Never cite kg projections for RPE-based sets. Use language like
  "RPE 8 prescribed" or "intensity-regulated volume".

Return JSON only:
{
  "stance": "continue | monitor | adjust | critical",
  "summary": "2-3 sentence plain English summary",
  "strengths": ["string"],
  "weaknesses": ["string"],
  "suggestions": [
    {
      "type": "string",
      "week": null,
      "phase": null,
      "exercise": null,
      "rationale": "string citing specific data"
    }
  ],
  "projected_readiness_at_comp": 78,
  "data_citations": ["string"]
}
```

---

### 8.4 Glossary Resolution

**Trigger:** Every import, after text extraction
**Model tier:** Air
**Tool:** `import_resolve_glossary`

**Input:**

```json
{
  "exercise_names_from_file": ["Squat", "RDL", "CGBench", "Tempo SQ", "LPDWN"],
  "existing_glossary": [
    { "id": "squat", "name": "Barbell Back Squat" },
    { "id": "romanian_deadlift", "name": "Romanian Deadlift" },
    { "id": "close_grip_bench_press", "name": "Close Grip Bench Press" },
    { "id": "lat_pulldown", "name": "Lat Pulldown" }
  ]
}
```

**Pre-pass note:** Before this AI call, run `rapidfuzz` token-sort ratio against glossary names. Any match ≥ 0.92 is resolved automatically without the AI call. Only unresolved names reach this prompt.

**System prompt:**

```
You are matching exercise names from a training spreadsheet to a
canonical exercise glossary.

RULES:
- Match abbreviations, common nicknames, and shorthand.
  Examples: "RDL" → Romanian Deadlift, "CGBench" → Close Grip Bench Press,
  "SLDL" → Stiff Leg Deadlift, "OHP" → Overhead Press
- confidence: 1.0 = certain, 0.85+ = high, below 0.85 = do not match
- If confidence < 0.85, set matched_id to null and suggest a new glossary entry
- suggested_new_entry: provide name, category, and equipment only.
  Do not invent muscle groups or fatigue profiles.
- category values: squat | bench | deadlift | back | chest | arm |
  legs | core | lower_back
- equipment values: barbell | dumbbell | cable | machine | bodyweight |
  hex_bar | bands | kettlebell

Return JSON only:
{
  "resolutions": [
    {
      "input": "string",
      "matched_id": "string | null",
      "confidence": 0.0-1.0,
      "method": "exact | abbreviation | nickname | no_match",
      "suggested_new_entry": {
        "name": "string",
        "category": "string",
        "equipment": "string"
      }
    }
  ]
}
```

---

## 9. Program Evaluation Prompt — Planned Session Serialization

This applies to the **existing** program evaluation AI call, not the template evaluation. The issue is that RPE-based planned sessions serialize with `kg: 0` or `kg: null`, which the model misreads as zero load.

### 9.1 Serialization Transform

Run this transform on all planned sessions before including them in the program evaluation prompt payload. Never send raw DynamoDB output for planned exercises.

```python
def serialize_planned_exercise_for_prompt(exercise: dict) -> dict:
    kg = exercise.get("kg") or 0
    rpe = exercise.get("rpe_target")
    load_source = exercise.get("load_source")

    if load_source == "rpe" or (kg == 0 and rpe is not None):
        return {
            "name": exercise["name"],
            "sets": exercise.get("sets"),
            "reps": exercise.get("reps"),
            "load": f"@RPE {rpe}",
            "load_type": "rpe",
            "rpe_target": rpe
        }
    elif load_source == "unresolvable" or (kg == 0 and rpe is None):
        return {
            "name": exercise["name"],
            "sets": exercise.get("sets"),
            "reps": exercise.get("reps"),
            "load": "unspecified",
            "load_type": "unspecified"
        }
    else:
        return {
            "name": exercise["name"],
            "sets": exercise.get("sets"),
            "reps": exercise.get("reps"),
            "load": f"{kg}kg",
            "load_type": "absolute",
            "kg": kg,
            "rpe_target": rpe
        }
```

**Example serialized output the model receives:**

```json
[
  { "name": "Squat",       "sets": 5, "reps": 3, "load": "@RPE 8",    "load_type": "rpe",         "rpe_target": 8.0 },
  { "name": "Bench Press", "sets": 3, "reps": 5, "load": "102.5kg",   "load_type": "absolute",    "kg": 102.5 },
  { "name": "RDL",         "sets": 3, "reps": 6, "load": "unspecified","load_type": "unspecified"              }
]
```

### 9.2 Program Evaluation Prompt Addition

Add the following block to the existing program evaluation system prompt, in the data interpretation section:

```
PLANNED SESSION INTERPRETATION:
- Sets with load_type "rpe": intensity-regulated. Do NOT treat as zero load.
  Estimate relative intensity for qualitative assessment only:
  RPE 10 ≈ 100%, RPE 9 ≈ 96%, RPE 8 ≈ 92%, RPE 7 ≈ 88% of current e1RM.
  Use language like "RPE 8 prescribed" — never cite a projected kg figure.
- Sets with load_type "absolute": use kg value as-is.
- Sets with load_type "unspecified": exclude from volume assessment entirely.
  Note their presence as a data gap if it affects a meaningful number of sets.
- When summarising future block load for an exercise that mixes absolute and
  RPE sets, describe them separately — do not aggregate into a single volume
  figure unless you can resolve both to the same intensity basis.
```

---

## 10. Block → Template Conversion

Converting an existing program block into a reusable template strips all temporal and athlete-specific data while preserving program structure.

```python
def convert_block_to_template(program: dict, e1rm_map: dict) -> dict:
    sessions = []
    for i, session in enumerate(program["sessions"]):
        if session.get("completed"):
            continue  # completed sessions stripped from template

        tpl_exercises = []
        for ex in session.get("planned_exercises", []):
            kg = ex.get("kg") or 0
            rpe = ex.get("rpe_target")
            e1rm = e1rm_map.get(ex["name"])
            load_source = ex.get("load_source", "absolute")

            if load_source == "rpe" or (kg == 0 and rpe):
                tpl_ex = {
                    "load_type": "rpe",
                    "load_value": None,
                    "rpe_target": rpe
                }
            elif kg > 0 and e1rm and e1rm > 0:
                tpl_ex = {
                    "load_type": "percentage",
                    "load_value": round(kg / e1rm, 3),
                    "rpe_target": rpe
                }
            elif kg > 0:
                tpl_ex = {
                    "load_type": "absolute",
                    "load_value": kg,
                    "rpe_target": rpe
                }
            else:
                tpl_ex = {
                    "load_type": "unresolvable",
                    "load_value": None,
                    "rpe_target": None
                }

            tpl_exercises.append({
                "name": ex["name"],
                "glossary_id": ex.get("glossary_id"),
                "sets": ex.get("sets"),
                "reps": ex.get("reps"),
                **tpl_ex,
                "notes": ex.get("notes", "")
            })

        sessions.append({
            "id": f"tpl_{uuid4()}",
            "week_number": derive_week_number(session, program),
            "day_of_week": session.get("day"),
            "day_index": derive_day_index(session, program),
            "label": session.get("week", ""),
            "exercises": tpl_exercises
        })

    return {
        "meta": {
            "derived_from_program_sk": program["sk"],
            "estimated_weeks": derive_week_count(program),
            "days_per_week": derive_days_per_week(program),
            "archived": False,
            "ai_evaluation": None
        },
        "phases": program.get("phases", []),
        "sessions": sessions
    }
```

**Stripping rules:**
- Completed sessions → excluded entirely
- `date`, `body_weight_kg`, `session_rpe`, `session_notes`, `videos`, `pain_log` → stripped
- `status`, `completed`, `block` → stripped
- Phase boundaries, week labels, exercise structure → preserved

---

## 11. Archive / Unarchive

Simple boolean flag operations. Both programs and templates support archiving.

### Programs

```python
# Archive
update program#vNNN: meta.archived = true, meta.archived_at = now()
# Does NOT change program#current — archiving a non-current version is a no-op on current pointer
# Archiving the current version: update program#current to point to most recent non-archived version

# Unarchive
update program#vNNN: meta.archived = false, meta.archived_at = null
```

**Rules:**
- Cannot archive the active current program version if it has incomplete planned sessions in the future — surface a warning, require confirmation
- Archived programs are hidden from default list views but accessible via filter
- Analytics do not run on archived programs

### Templates

```python
# Archive
update template#vNNN: meta.archived = true
update template#current_list: set archived = true on matching entry

# Unarchive
update template#vNNN: meta.archived = false
update template#current_list: set archived = false on matching entry
```

---

## 12. Onboarding Gate

Required before template application is permitted. The three SBD maxes are the hard gate.

```
Mandatory (hard block on template application):
├── Squat e1RM or recent best set (weight × reps for conservative estimate)
├── Bench e1RM or recent best set
├── Deadlift e1RM or recent best set
├── Bodyweight (kg)
└── Sex (required for DOTS polynomial)

Strongly recommended (improves AI backfill accuracy):
├── Lift profiles: style notes + sticking points per SBD lift
├── Height + limb lengths
└── Upcoming competition date

Optional (improves template evaluation quality):
├── Training history length (years lifting, years competing)
├── Current weekly training frequency
└── Primary goal (total PR / weight class move / first comp / general)
```

If a user attempts to apply a template without SBD maxes stored, show a blocking modal with a direct link to the mandatory form. Do not silently default to zero or skip the gate.

---

## 13. Backend API

```
# Import lifecycle
POST   /api/import/upload
       Accepts: multipart/form-data (file)
       → hash check → pending check → classify → parse → stage
       Returns: { import_id, classification, preview, warnings }

GET    /api/import/pending
       Returns: current awaiting_review imports (one per import_type)

GET    /api/import/:import_id
       Returns: full staged import with diff and preview

POST   /api/import/:import_id/apply
       Body: { merge_strategy, conflict_resolutions, start_date? }
       → write new program or template version
       → mark pending as applied

POST   /api/import/:import_id/reject
       Body: { reason? }
       → mark pending as rejected, unblock new imports of same type

# Template library
GET    /api/templates
       Returns: template#current_list (default: archived=false)
       Query: ?include_archived=true

GET    /api/templates/:sk
       Returns: full template detail

POST   /api/templates
       Body: full template object | { from_program_sk }
       → create from scratch or convert block

POST   /api/templates/:sk/copy
       → duplicates template with new version SK

PATCH  /api/templates/:sk/archive
PATCH  /api/templates/:sk/unarchive

# Template evaluation
POST   /api/templates/:sk/evaluate
       → trigger async AI evaluation
       Returns: { job_id }

GET    /api/templates/:sk/evaluate/status
       → poll evaluation result
       Returns: { status: pending|complete, result? }

# Template application
POST   /api/templates/:sk/apply
       Body: { target, start_date, week_start_day }
       → run max resolution gate
       Returns: { missing_maxes[] } | { preview: concretized_sessions[] }

POST   /api/templates/:sk/apply/confirm
       Body: { backfilled_maxes?, day_mapping_confirmed: true }
       → write new program version
       Returns: { program_sk }

# Program archive
PATCH  /api/programs/:sk/archive
PATCH  /api/programs/:sk/unarchive

# Glossary
POST   /api/glossary/exercises
       → add new exercise entry

PATCH  /api/glossary/exercises/:id
       → update exercise (includes manual e1rm_estimate set)

POST   /api/glossary/exercises/:id/estimate-fatigue
       → trigger AI fatigue profile estimation for single exercise

POST   /api/glossary/exercises/:id/estimate-e1rm
       → trigger AI e1rm backfill for single exercise
```

---

## 14. Agent Tools (`health_write` specialist additions)

These mirror every portal action so the full feature is accessible from Discord.

| Tool | Arguments | Description |
|---|---|---|
| `import_parse_file` | `s3_key` or `base64_content`, `filename` | Full parse pipeline, returns import_id |
| `import_apply` | `import_id`, `merge_strategy`, `conflict_resolutions?`, `start_date?` | Apply staged import |
| `import_reject` | `import_id`, `reason?` | Reject staged import |
| `import_list_pending` | — | List all awaiting_review imports |
| `template_list` | `include_archived?` | List templates |
| `template_get` | `sk` | Get full template detail |
| `template_apply` | `sk`, `target`, `start_date`, `week_start_day` | Apply template to block, returns gate result or preview |
| `template_apply_confirm` | `sk`, `backfilled_maxes?` | Confirm and write concretized block |
| `template_evaluate` | `sk` | Trigger AI evaluation, returns result synchronously (heavy model) |
| `template_create_from_block` | `program_sk?`, `name` | Convert current or specified block to template |
| `template_copy` | `sk`, `new_name` | Duplicate a template |
| `template_archive` | `sk` | Archive template |
| `template_unarchive` | `sk` | Unarchive template |
| `program_archive` | `sk` | Archive a program version |
| `program_unarchive` | `sk` | Unarchive a program version |
| `glossary_add` | `exercise` object | Add new exercise to glossary |
| `glossary_update` | `id`, `fields` | Update exercise fields |
| `glossary_set_e1rm` | `id`, `value_kg`, `method?` | Manually set e1rm_estimate |
| `glossary_estimate_e1rm` | `id` | AI backfill e1rm for one exercise |
| `glossary_estimate_fatigue` | `id` | AI fatigue profile estimation for one exercise |

---

## 15. Frontend Component Map

```
ImportWizard/
├── Step1_Upload
│   ├── File drop zone (.xlsx, .csv only)
│   ├── Duplicate file error state (shows existing import/template link)
│   └── Pending import blocker (shows pending item with Apply/Reject actions)
│
├── Step2_Classification
│   ├── Auto-detected type badge (Template / Session Import)
│   └── Ambiguity resolution panel (shown only when AI returns "ambiguous")
│       └── Side-by-side interpretation cards, user selects one
│
├── Step3_GlossaryReview
│   ├── Resolution table: input name → matched glossary entry
│   ├── Confidence badge per row (exact / abbreviation / no_match)
│   ├── Manual override dropdown (search glossary)
│   └── Auto-add candidates list (user confirms additions)
│
├── Step4_Preview
│   ├── TemplatePreview
│   │   ├── Week × day grid
│   │   ├── load_type badges: RPE (blue) / % (green) / absolute (orange) / unresolvable (red)
│   │   └── Warning panel (absolute weights in template, missing load info)
│   └── SessionDiff
│       ├── New sessions (green)
│       ├── Conflict sessions (yellow, expandable)
│       └── Protected completed sessions (grey, locked icon)
│
├── Step5_ConflictResolve  [session import only]
│   ├── Per-conflict row: Keep / Replace / Merge radio
│   └── Overall strategy selector (Selective / Replace non-completed / Append only)
│
└── Step6_Apply
    └── Final summary + confirm button

TemplateLibrary/
├── TemplateCard
│   ├── Name, week count, days/week
│   ├── Evaluation stance badge (coloured: continue=green, monitor=yellow,
│   │   adjust=orange, critical=red)
│   └── Actions: Evaluate / Apply / Copy / Archive
│
├── TemplateDetail
│   ├── Session grid (week × day, exercise list per cell)
│   ├── load_type legend
│   └── EvaluationPanel
│       ├── Stance badge + summary
│       ├── Strengths list
│       ├── Weaknesses list
│       ├── Suggestions list (each with rationale)
│       └── "Re-evaluate" button (triggers fresh AI call)
│
└── ApplyModal
    ├── Target selector (New block / Append / Replace non-completed)
    ├── Start date picker
    ├── Week starts on: Saturday / Monday / Sunday
    └── MaxResolutionGate (shown inline if gate fails)
        ├── Missing exercises list
        ├── Per-exercise: [Enter manually] [AI estimate]
        └── Proceed button (enabled once all resolved)

GlossaryManager/
├── ExerciseTable
│   ├── Columns: name, category, equipment, fatigue_profile_source,
│   │   e1rm_estimate (value + confidence badge), actions
│   └── Filter by: category, fatigue_source, has_e1rm
│
├── ExerciseEditModal
│   ├── All glossary fields
│   ├── e1rm_estimate section:
│   │   ├── Current value + confidence + basis
│   │   ├── Manual override input
│   │   └── "AI Estimate" button
│   └── "Estimate Fatigue Profile" button (if source = pending)
│
└── AutoAddReview
    ├── Cards for each AI-suggested new entry
    ├── Editable fields before confirming
    └── Confirm all / Confirm individually / Reject

ProgramActions/  [additions to existing program toolbar]
├── Archive / Unarchive button
├── Convert to Template button
│   └── Name input modal → triggers block→template conversion

SessionCard/  [additions to existing planned session display]
└── Exercise load display:
    ├── load_source = "absolute"    → "102.5 kg"
    ├── load_source = "rpe"         → "@ RPE 8"
    ├── load_source = "percentage"  → "~102.5 kg  (75%)"  [greyed, ~ prefix]
    └── load_source = "unresolvable"→ "—"  [dash, grey]
```

---

## 16. Implementation Notes

| Area | Decision | Rationale |
|---|---|---|
| File extraction | Python backend (openpyxl) | AI call happens server-side, consistent with existing Python tools layer |
| Fuzzy pre-match | `rapidfuzz` token-sort, threshold 0.92 before AI glossary call | Reduces AI token cost for common abbreviations |
| S3 storage | Store original file under `imports/{import_id}/{filename}` | Enables re-parse without re-upload if parse logic changes |
| Pending lock | One per `import_type`, hard block | Prevents spamming; forces deliberate apply/reject |
| No-mutate rule | Always write `program#vNNN+1` on session import apply | Consistent with existing DynamoDB schema rules |
| TTL | 7-day DynamoDB TTL on `import#pending` | Auto-cleanup, no cron required |
| RPE backfill | Never stored as `kg` at import time for RPE sets | Stale by week 3 if stored; runtime resolution always uses current e1RM |
| `load_source` | Carried from template → concretized session | Enables future re-concretization if e1RM updates significantly |
| Completed protection | Hard lock in conflict detection, no override | Non-negotiable data integrity |
| Template version counter | `template#current_list` entry count + 1 | Same pattern as `program#current` pointer |
| Absolute weights warning | Flag not block for templates | May be intentional (e.g. comp openers embedded in program) |
| e1RM estimate confidence | Always `"low"` for AI backfill until user confirms | Honest about estimate quality, never silently trusted |