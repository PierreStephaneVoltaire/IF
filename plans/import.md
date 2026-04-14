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
| **Max Resolution Gate** | A hard block on Template → Block application when a required exercise has no e1RM or glossary estimate available. Only fires at application time, never at import or template save time. |
| **Pending Import** | A staged, unconfirmed import record. One allowed per import type at a time. Must be applied or rejected before a new import of the same type can be submitted. |
| **Glossary** | The canonical exercise registry (`glossary#v1`). Source of truth for exercise identity, fatigue profiles, and e1RM estimates used in concretization. |
| **e1RM Estimate** | A per-exercise estimated one-rep max stored on the glossary entry. Used when no logged e1RM exists. May be manually set or AI estimated. Only relevant at concretization time. |
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
    "absolute load_type means the source file had hard kg numbers — flag for user review, it may still be a valid template (e.g. comp openers embedded)",
    "glossary_id null = unresolved exercise, auto-added to glossary as minimal entry on import apply",
    "ai_evaluation is null until user explicitly requests evaluation"
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
  "import_type": "template",
  "status": "awaiting_review",
  "source_filename": "sheiko_37.xlsx",
  "source_file_hash": "sha256:abc123...",
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
    "Hash check on upload prevents re-submitting the same file while a pending exists for it"
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

| `load_source` | `kg` | `rpe_target` | Meaning |
|---|---|---|---|
| `"absolute"` | present | optional | Hard number from program |
| `"rpe"` | `null` | present | Resolve at runtime from e1RM |
| `"percentage"` | computed at concretization | optional | Was `%` in template, kg computed at apply time |
| `"unresolvable"` | `null` | `null` | No load info — exclude from projections |

`"percentage"` sets have their `kg` computed and stored at template-apply time using the e1RM at that moment. They are functionally identical to `"absolute"` after concretization. The distinction is retained for lineage only.

#### `glossary` exercises — add `e1rm_estimate`

```json
{
  "id": "romanian_deadlift",
  "name": "Romanian Deadlift",
  "e1rm_estimate": 145.0,
  "e1rm_estimate_basis": "0.78 × deadlift (220kg) — hip hinge, similar leverages",
  "e1rm_estimate_set_at": "2026-04-14T19:42:08+00:00"
}
```

Either the field is present with a number or it is absent. No confidence tiers. The basis string is for the user's reference only — it does not affect any downstream logic. The gate at application time either passes or it doesn't.

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

## 4. Import Flows

### 4.1 Template Import

The file goes to the agent. The agent returns structured JSON matching the template session schema. No deterministic pre-parsing, no client-side extraction.

```
User uploads file
  │
  ├── Hash check
  │     Duplicate file hash already in template#current_list?
  │     → block, show existing template with link
  │
  ├── Pending check
  │     import#pending with import_type="template" and status="awaiting_review" exists?
  │     → block, show pending item with Apply / Reject actions
  │
  ├── Agent parse (see §6.1)
  │     File content + required output schema → structured template JSON
  │     Agent also identifies load_type per exercise and flags absolute weights
  │
  ├── Glossary resolution
  │     For each exercise name in agent output:
  │       ├── Match against existing glossary entries by name
  │       ├── Match found → link glossary_id
  │       └── No match → queue as auto_add_candidate
  │     Output: resolved[], auto_add_candidates[], resolution_status
  │
  ├── Stage as import#pending
  │     status: "awaiting_review"
  │     TTL: 7 days
  │
  ├── User review (UI)
  │     ├── Week × day session grid preview
  │     ├── load_type badge per exercise (RPE / % / absolute / unresolvable)
  │     ├── Absolute weight warning if any exercises have load_type "absolute"
  │     ├── Glossary resolution status — unresolved exercises listed for review
  │     ├── Manual name mapping overrides for glossary mismatches
  │     └── Apply or Reject
  │
  └── On Apply
        ├── Increment template version counter
        ├── Write template#vNNN
        ├── Update template#current_list
        ├── Auto-add unresolved exercises to glossary as minimal entries
        │     (fatigue_profile fields absent — user triggers AI estimation separately)
        ├── Mark import#pending as applied
        └── Unblock new template imports
```

### 4.2 Session Import

```
User uploads file
  │
  ├── Hash check + Pending check (same as template, import_type="session_import")
  │
  ├── Agent parse (see §6.1)
  │     File content + required output schema → list of session objects with dates
  │
  ├── Glossary resolution (same as template flow)
  │
  ├── Conflict detection
  │     For each imported session date against current program sessions:
  │       ├── Completed session at that date → PROTECT (hard lock, never overwrite)
  │       ├── Planned session at that date → CONFLICT (user resolves per session)
  │       └── No existing session at that date → SAFE (add freely)
  │
  ├── Stage as import#pending
  │     Includes full diff: safe / conflict / protected counts and detail
  │     TTL: 7 days
  │
  ├── User review (UI)
  │     ├── Per-conflict session resolution:
  │     │     ├── Keep existing planned
  │     │     ├── Replace with import
  │     │     └── Merge (keep both as variants — both marked planned)
  │     ├── Protected completed sessions shown greyed, locked, no action available
  │     └── Overall merge strategy selector:
  │           ├── Selective (honour per-session choices above)
  │           ├── Replace non-completed only (bulk replace, skip completed)
  │           └── Append only (add new dates, skip all conflicts entirely)
  │
  └── On Apply
        ├── Write new program#vNNN (never mutate existing version in place)
        ├── Apply conflict resolutions
        ├── All completed sessions carried over untouched
        ├── Update program#current ref_sk
        ├── Mark import#pending as applied
        └── Async: recalculate analytics for affected weeks
```

### 4.3 Template → Block Application

This is separate from import. The template already exists. The user is turning it into a live planned block.

```
User selects template → clicks "Apply to Block"
  │
  ├── Choose application target:
  │     ├── New block
  │     │     Archive current program → create fresh program#vNNN
  │     ├── Append to current block
  │     │     Add concretized sessions after last existing planned session date
  │     └── Replace non-completed in current block
  │           Overwrite planned sessions, preserve completed
  │
  ├── Set start date + week_start_day (Saturday / Monday / Sunday)
  │
  ├── Max Resolution Gate
  │     Collect required_maxes from template
  │     For each:
  │       ├── SBD lifts → check current_maxes (always present post-onboarding)
  │       ├── Accessories → check glossary entry for e1rm_estimate
  │       └── Missing → HARD BLOCK
  │             Show modal:
  │             "These exercises need a max before weights can be calculated:
  │              [Romanian Deadlift]  [Enter manually]  [AI estimate]
  │              [Tempo Squat]        [Enter manually]  [AI estimate]"
  │             Proceed button disabled until all resolved
  │
  ├── Concretize sessions
  │     Map week_number + day_of_week → calendar dates
  │     using start_date and week_start_day
  │     For each exercise in each session:
  │       ├── load_type "rpe"
  │       │     kg: null, rpe_target: value, load_source: "rpe"
  │       ├── load_type "percentage"
  │       │     kg: round_to_2_5(e1rm × load_value)
  │       │     load_source: "percentage"
  │       ├── load_type "absolute"
  │       │     kg: value, load_source: "absolute"
  │       └── load_type "unresolvable"
  │             kg: null, load_source: "unresolvable"
  │     All sessions: status "planned", completed: false
  │
  ├── Preview concretized calendar to user
  │
  └── On Confirm
        ├── Write new program#vNNN
        ├── Store template_lineage on meta
        └── Update program#current ref_sk
```

---

## 5. Block → Template Conversion

Converting an existing program block into a reusable template strips all temporal and athlete-specific data while preserving structure.

**Stripping rules:**
- Completed sessions → excluded entirely from the template
- `date`, `body_weight_kg`, `session_rpe`, `session_notes`, `videos`, `pain_log` → stripped
- `status`, `completed`, `block` → stripped
- Phase boundaries, week labels, exercise names, set/rep structure → preserved

**Load conversion per exercise:**

| Condition | Template `load_type` | Template `load_value` |
|---|---|---|
| `load_source = "rpe"` or `kg = null` and `rpe_target` present | `"rpe"` | `null` |
| `kg > 0` and e1RM known for that lift | `"percentage"` | `round(kg / e1rm, 3)` |
| `kg > 0` and no e1RM available | `"absolute"` | `kg` |
| Neither kg nor RPE | `"unresolvable"` | `null` |

**Week mapping:**

Sessions get `week_number` derived from their date offset from the program start date, and `day_of_week` from their `day` field. No calendar dates are stored on the template.

---

## 6. Agent Calls

### 6.1 File Parse (Template and Session Import)

**Trigger:** File upload, after hash and pending checks pass  
**Model tier:** Standard  
**Agent tool:** `import_parse_file`  
**Caller tells the agent which mode:** `"template"` or `"session_import"` — either from pre-classification heuristic or explicit user selection if ambiguous

The file is extracted to text server-side (openpyxl on the Python backend) and sent as structured content. The agent returns JSON matching the required schema. No deterministic parsing — the agent reads whatever format the spreadsheet uses.

**System prompt:**

```
You are parsing a powerlifting training spreadsheet into structured JSON.

MODE: {mode}  (template | session_import)

TEMPLATE MODE RULES:
- Sessions have no calendar dates. Use week_number (integer, 1-based)
  and day_of_week (Monday/Tuesday/etc) only.
- load_type per exercise:
    "rpe"         — load expressed as RPE target (@8, RPE 8, etc.)
    "percentage"  — load expressed as % of max (75%, 0.75, etc.)
    "absolute"    — hard kg value present (flag this as a warning —
                    it may be intentional but the user should confirm)
    "unresolvable"— no load information present at all
- load_value: decimal for percentage (0.75 not 75%), null for rpe/unresolvable
- rpe_target: numeric (8.0), null if not RPE-based

SESSION IMPORT MODE RULES:
- Sessions have real calendar dates (YYYY-MM-DD).
- All loads are absolute kg values.
- Include RPE if present in the source, null if absent.
- status: "planned" for future dates, "completed" for past dates
  (use file context — logged results, notes — to determine, not just date).

BOTH MODES:
- Do not invent data not present in the source file.
- If a field is genuinely absent, use null.
- Identify phase boundaries if the file has them (week ranges with labels).
- exercises[].name: use the name exactly as written in the file.
  Glossary matching happens separately — do not normalise names.

WARNINGS to include:
- absolute_weights_in_template: exercise names with hard kg in template mode
- missing_load_info: exercises with no load information of any kind
- unrecognised_structure: anything structurally ambiguous

Return JSON only. No prose. No markdown fences.

Required schema:
{
  "parse_notes": "brief description of what was detected",
  "estimated_weeks": integer,
  "days_per_week": integer,
  "phases": [
    {
      "name": "string",
      "week_start": integer,
      "week_end": integer,
      "intent": "string | null"
    }
  ],
  "sessions": [
    {
      "week_number": "integer (template) | null (session_import)",
      "date": "YYYY-MM-DD (session_import) | null (template)",
      "day_of_week": "Monday | Tuesday | ...",
      "day_index": "integer, 1-based within week",
      "label": "string e.g. W1D1",
      "exercises": [
        {
          "name": "string — exact name from file",
          "sets": integer,
          "reps": integer,
          "load_type": "rpe | percentage | absolute | unresolvable",
          "load_value": "decimal | null",
          "rpe_target": "number | null",
          "notes": "string | null"
        }
      ]
    }
  ],
  "warnings": [
    {
      "type": "string",
      "exercises": ["string"],
      "message": "string"
    }
  ]
}
```

---

### 6.2 AI Max Estimate for Accessories

**Trigger:** Max Resolution Gate finds a missing e1RM, user clicks "AI estimate"  
**Model tier:** Air  
**Agent tool:** `import_estimate_accessory_max`

Only called for individual exercises when the user explicitly requests it. Not called automatically.

**System prompt:**

```
You are estimating a one-rep max for a powerlifting accessory exercise
based on an athlete's competition lift maxes.

Use biomechanical reasoning — relate the accessory to its closest primary
lift by movement pattern and muscle overlap. Be conservative.
Underestimating is always safer than overestimating for weight prescription.

Input:
{
  "exercise": "Romanian Deadlift",
  "current_maxes": { "squat": 185, "bench": 115, "deadlift": 220 },
  "lift_profiles": [...],
  "body_metrics": { "height_cm": 175.5, "leg_length_cm": 100.0 }
}

Return JSON only:
{
  "e1rm_kg": 145.0,
  "basis": "0.78 × deadlift (220kg) — hip hinge pattern, similar leverages"
}
```

The returned `e1rm_kg` is stored directly as `glossary.e1rm_estimate`. The `basis` string is stored as `glossary.e1rm_estimate_basis` for the user's reference.

---

### 6.3 Template Evaluation

**Trigger:** User explicitly requests evaluation on a saved template  
**Model tier:** Heavy  
**Agent tool:** `import_evaluate_template`

Not called at import time. Not called automatically after apply. User-initiated only.

**System prompt:**

```
You are evaluating a powerlifting training template against an athlete's
current profile and competition timeline.

RULES:
- Be specific and data-cited. Reference weeks, phases, exercises by name.
- stance values:
    "continue"  — template is well-matched to athlete and timeline
    "monitor"   — viable but specific elements to watch
    "adjust"    — changes recommended before applying
    "critical"  — poorly matched or potentially harmful
- strengths and weaknesses: minimum 2 each where data supports it
- suggestions: each must cite the specific data point motivating it
- If context fields are null or absent, note missing context and
  reduce scope of assessment accordingly. Do not refuse to evaluate.

PLANNED SESSION INTERPRETATION:
- load_type "rpe": intensity-regulated. Do not treat as zero load.
  Estimate relative intensity for qualitative assessment only:
  RPE 10 ≈ 100%, RPE 9 ≈ 96%, RPE 8 ≈ 92%, RPE 7 ≈ 88% of current e1RM.
  Use language like "RPE 8 prescribed" — never cite projected kg figures.
- load_type "percentage": use load_value × e1RM for intensity estimate.
- load_type "unresolvable": exclude from volume assessment, note as data gap.

Return JSON only:
{
  "stance": "continue | monitor | adjust | critical",
  "summary": "2-3 sentence plain English summary",
  "strengths": ["string"],
  "weaknesses": ["string"],
  "suggestions": [
    {
      "type": "string",
      "week": "integer | null",
      "phase": "string | null",
      "exercise": "string | null",
      "rationale": "string — must cite specific data"
    }
  ],
  "projected_readiness_at_comp": "integer 0-100 | null",
  "data_citations": ["string"]
}
```

---

## 7. Program Evaluation Prompt — Planned Session Serialization

This applies to the **existing** program evaluation AI call. RPE-based planned sessions currently serialize with `kg: 0` or `kg: null`, which the model misreads as zero load. Two fixes applied together.

### 7.1 Serialization Transform

Run on all planned sessions before including them in the program evaluation prompt. Never send raw DynamoDB output for planned exercises.

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

**What the model receives:**

```json
[
  { "name": "Squat",       "sets": 5, "reps": 3, "load": "@RPE 8",     "load_type": "rpe",         "rpe_target": 8.0 },
  { "name": "Bench Press", "sets": 3, "reps": 5, "load": "102.5kg",    "load_type": "absolute",    "kg": 102.5       },
  { "name": "RDL",         "sets": 3, "reps": 6, "load": "unspecified","load_type": "unspecified"                    }
]
```

### 7.2 Program Evaluation Prompt Addition

Add to the existing program evaluation system prompt in the data interpretation section:

```
PLANNED SESSION INTERPRETATION:
- Sets with load_type "rpe": intensity-regulated. Do NOT treat as zero load.
  Estimate relative intensity for qualitative assessment only:
  RPE 10 ≈ 100%, RPE 9 ≈ 96%, RPE 8 ≈ 92%, RPE 7 ≈ 88% of current e1RM.
  Use language like "RPE 8 prescribed" — never cite a projected kg figure.
- Sets with load_type "absolute": use kg value as-is.
- Sets with load_type "unspecified": exclude from volume assessment entirely.
  Note their presence as a data gap if they represent a significant portion
  of planned sessions.
- When an exercise mixes absolute and RPE sets across weeks, describe them
  separately — do not aggregate into a single volume figure.
```

---

## 8. Archive / Unarchive

Simple boolean flag. Both programs and templates support it.

### Programs

```
Archive program#vNNN:
  meta.archived = true
  meta.archived_at = now()

  If vNNN is the current version:
    Update program#current to point to most recent non-archived version
    If no non-archived version exists: require user to unarchive one first

Unarchive program#vNNN:
  meta.archived = false
  meta.archived_at = null
```

Archived programs are excluded from default list views. A filter exposes them. Analytics do not run against archived programs.

### Templates

```
Archive template#vNNN:
  meta.archived = true
  Update template#current_list entry: archived = true

Unarchive template#vNNN:
  meta.archived = false
  Update template#current_list entry: archived = false
```

---

## 9. Block → Template Conversion

```python
def convert_block_to_template(program: dict, e1rm_map: dict) -> dict:
    sessions = []
    for session in program["sessions"]:
        if session.get("completed"):
            continue  # completed sessions excluded from template

        tpl_exercises = []
        for ex in session.get("planned_exercises", []):
            kg = ex.get("kg") or 0
            rpe = ex.get("rpe_target")
            load_source = ex.get("load_source", "absolute")
            e1rm = e1rm_map.get(ex["name"])

            if load_source == "rpe" or (kg == 0 and rpe):
                load_type = "rpe"
                load_value = None
            elif kg > 0 and e1rm and e1rm > 0:
                load_type = "percentage"
                load_value = round(kg / e1rm, 3)
            elif kg > 0:
                load_type = "absolute"
                load_value = kg
            else:
                load_type = "unresolvable"
                load_value = None

            tpl_exercises.append({
                "name": ex["name"],
                "glossary_id": ex.get("glossary_id"),
                "sets": ex.get("sets"),
                "reps": ex.get("reps"),
                "load_type": load_type,
                "load_value": load_value,
                "rpe_target": rpe,
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

---

## 10. Onboarding Gate

Required before any template can be applied to a block. Never checked at template import or save time.

```
Hard block on template application:
  ├── Squat e1RM or recent best set
  ├── Bench e1RM or recent best set
  ├── Deadlift e1RM or recent best set
  ├── Bodyweight (kg)
  └── Sex (required for DOTS polynomial)

Strongly recommended (improves AI estimate accuracy):
  ├── Lift profiles: style notes + sticking points per SBD lift
  ├── Height + limb lengths
  └── Upcoming competition date

Optional (improves template evaluation quality):
  ├── Training history length
  ├── Current weekly training frequency
  └── Primary goal
```

If a user attempts to apply a template without SBD maxes, show a blocking modal with a direct link to the onboarding form. No silent defaults.

---

## 11. Backend API

```
# Import lifecycle
POST   /api/import/upload
       Accepts: multipart/form-data (file, mode: "template"|"session_import")
       → hash check → pending check → agent parse → stage
       Returns: { import_id, preview, warnings }

GET    /api/import/pending
       Returns: all awaiting_review imports

GET    /api/import/:import_id
       Returns: full staged import with diff and preview

POST   /api/import/:import_id/apply
       Body: { merge_strategy?, conflict_resolutions? }
       → write template or program version → mark pending applied

POST   /api/import/:import_id/reject
       Body: { reason? }
       → mark pending rejected, unblock new imports of same type

# Template library
GET    /api/templates
       Query: ?include_archived=true
       Returns: template#current_list

GET    /api/templates/:sk
       Returns: full template

POST   /api/templates
       Body: full template object | { from_program_sk, name }
       → create from scratch or convert block to template

POST   /api/templates/:sk/copy
       Body: { name }
       → duplicate template with new version SK

PATCH  /api/templates/:sk/archive
PATCH  /api/templates/:sk/unarchive

# Template evaluation
POST   /api/templates/:sk/evaluate
       → agent evaluation call (synchronous, heavy model)
       Returns: evaluation result written to template meta + returned in response

# Template application
POST   /api/templates/:sk/apply
       Body: { target, start_date, week_start_day }
       → run max resolution gate
       Returns: { missing_maxes: [] } on gate fail
                { preview: concretized_sessions[] } on gate pass

POST   /api/templates/:sk/apply/confirm
       Body: { resolved_maxes?: {}, confirmed: true }
       → write new program version
       Returns: { program_sk }

# Program archive
PATCH  /api/programs/:sk/archive
PATCH  /api/programs/:sk/unarchive

# Glossary
POST   /api/glossary/exercises
       → add exercise entry

PATCH  /api/glossary/exercises/:id
       → update exercise fields

POST   /api/glossary/exercises/:id/estimate-e1rm
       Body: { current_maxes, lift_profiles, body_metrics }
       → agent AI estimate → store and return

POST   /api/glossary/exercises/:id/estimate-fatigue
       → existing AI fatigue estimation tool, unchanged
```

---

## 12. Agent Tools (`health_write` specialist additions)

| Tool | Arguments | Description |
|---|---|---|
| `import_parse_file` | `s3_key` or `base64_content`, `filename`, `mode` | Full parse pipeline, returns import_id and preview |
| `import_apply` | `import_id`, `merge_strategy?`, `conflict_resolutions?` | Apply staged import |
| `import_reject` | `import_id`, `reason?` | Reject staged import |
| `import_list_pending` | — | List all awaiting_review imports |
| `template_list` | `include_archived?` | List templates from current_list |
| `template_get` | `sk` | Full template detail |
| `template_apply` | `sk`, `target`, `start_date`, `week_start_day` | Run gate + return preview or missing maxes |
| `template_apply_confirm` | `sk`, `resolved_maxes?` | Write concretized block |
| `template_evaluate` | `sk` | Agent evaluation, writes result to template meta |
| `template_create_from_block` | `program_sk?`, `name` | Convert block to template |
| `template_copy` | `sk`, `new_name` | Duplicate a template |
| `template_archive` | `sk` | Archive template |
| `template_unarchive` | `sk` | Unarchive template |
| `program_archive` | `sk` | Archive a program version |
| `program_unarchive` | `sk` | Unarchive a program version |
| `glossary_add` | exercise object | Add new exercise |
| `glossary_update` | `id`, fields | Update exercise fields |
| `glossary_set_e1rm` | `id`, `value_kg`, `basis?` | Manually set e1rm_estimate |
| `glossary_estimate_e1rm` | `id` | AI estimate for one exercise |
| `glossary_estimate_fatigue` | `id` | AI fatigue profile for one exercise |

---

## 13. Frontend Component Map

```
ImportWizard/
├── Step1_Upload
│     File drop zone (.xlsx, .csv)
│     Mode selector: Template / Session Import
│     Duplicate file error state (links to existing template)
│     Pending import blocker (shows pending item, Apply / Reject inline)
│
├── Step2_GlossaryReview
│     Table: exercise name from file → matched glossary entry
│     Unresolved exercises listed with manual override dropdown
│     Auto-add candidates: user confirms before adding to glossary
│
├── Step3_Preview
│     TemplatePreview
│       Week × day session grid
│       load_type badge per exercise:
│         RPE (blue) / % (green) / absolute (orange) / unresolvable (red)
│       Warning panel: absolute weights in template, missing load info
│     SessionDiff
│       New sessions (green)
│       Conflict sessions (yellow, expandable with per-session resolution)
│       Protected completed sessions (grey, locked)
│
├── Step4_ConflictResolve  [session import only]
│     Per-conflict: Keep existing / Replace / Merge radio
│     Overall strategy: Selective / Replace non-completed / Append only
│
└── Step5_Apply
      Summary of changes
      Confirm button


TemplateLibrary/
├── TemplateCard
│     Name, week count, days/week
│     Evaluation stance badge: continue (green) / monitor (yellow) /
│       adjust (orange) / critical (red) / not evaluated (grey)
│     Actions: Evaluate / Apply / Copy / Archive
│
├── TemplateDetail
│     Full session grid (week × day)
│     load_type legend
│     EvaluationPanel
│       Stance badge + summary text
│       Strengths list
│       Weaknesses list
│       Suggestions (each with rationale)
│       Re-evaluate button
│
└── ApplyModal
      Target: New block / Append / Replace non-completed
      Start date picker
      Week starts on: Saturday / Monday / Sunday
      MaxResolutionGate (inline, shown only when gate fails)
        Missing exercises listed
        Per exercise: [Enter manually] input  or  [AI estimate] button
        Proceed enabled only when all resolved


GlossaryManager/
├── ExerciseTable
│     Columns: name, category, equipment, fatigue_profile_source,
│              e1rm_estimate (value or "—"), actions
│     Filter: category, has e1rm estimate, fatigue source
│
├── ExerciseEditModal
│     All glossary fields
│     e1rm_estimate section:
│       Current value + basis string
│       Manual override input
│       AI Estimate button (calls estimate-e1rm endpoint)
│     Estimate Fatigue Profile button (if fatigue_profile_source = "pending")
│
└── AutoAddReview
      Cards for each AI-suggested new exercise
      Editable name, category, equipment before confirming
      Confirm all / Confirm individually / Reject


ProgramActions/  [additions to existing program toolbar]
  Archive / Unarchive toggle
  Convert to Template button → name input modal → POST /api/templates


SessionCard/  [planned session display additions]
  load_source "absolute"     → "102.5 kg"
  load_source "rpe"          → "@ RPE 8"
  load_source "percentage"   → "~102.5 kg  (75%)"  greyed, tilde prefix
  load_source "unresolvable" → "—"  grey dash
```

---

## 14. Implementation Notes

| Decision | Rationale |
|---|---|
| Agent parses the file — no deterministic extraction | Templates come in arbitrary formats; an agent with a required output schema handles this without brittle column-mapping logic |
| Mode passed to agent by caller | User selects template vs session import on upload — agent does not need to guess |
| Max gate only at application time | The template is structure only; maxes are irrelevant until weights need to be computed |
| e1rm_estimate is a plain number, no confidence field | Confidence tiers that do not change any downstream logic add complexity with no benefit |
| Completed sessions hard-locked in session import | Non-negotiable data integrity — logged training history is never overwritten |
| Always write new program#vNNN on session import apply | Consistent with existing no-mutate-in-place schema rule |
| RPE sets: kg never stored at import time | kg computed from e1RM at concretization time for percentage sets only; RPE sets resolve at runtime using current e1RM so they stay accurate as the athlete progresses |
| Pending lock: one per import_type | Forces deliberate apply/reject; prevents accidental duplicate imports |
| 7-day DynamoDB TTL on import#pending | Auto-cleanup with no cron job required |
| Original file stored in S3 under imports/ prefix | Enables re-parse if parse logic changes without requiring re-upload |
| Absolute weights in templates are a warning not a block | May be intentional (e.g. comp openers hardcoded in a peaking program) |
| template#current_list as index | Avoids full table scan to list templates; same pattern as program#current pointer |