# Program Designer & Analytics Redesign

**Date:** 2026-04-09
**Status:** Draft

## Context

The current analytics algorithms compute metrics from data that barely exists in the program: RPE is logged in only 17% of sessions, bodyweight in 6%, phases lack `target_rpe` and `days_per_week` fields, and there is no distinction between planned sessions and actual performed work. The fatigue index, compliance score, and meet projection are all based on phantom data.

This redesign introduces:
1. A **planned vs actual** session model so compliance is measurable
2. Exercise **fatigue categories** in the glossary for proper load tracking
3. Rewritten analytics that use only real training data
4. A **program designer** page for building sessions ahead of time

## DynamoDB Schema Changes

### Program item (`pk=operator, sk=program#v{N}`)

All changes are additive — existing fields remain for backward compatibility.

#### Phase enrichment

Phases gain optional metadata fields:

```jsonc
{
  "name": "Base Build",
  "start_week": 2,
  "end_week": 4,
  "intent": "Progressive overload, volume accumulation",
  "target_rpe_min": 6,        // NEW - optional, int
  "target_rpe_max": 8,        // NEW - optional, int
  "days_per_week": 4,         // NEW - optional, int
  "notes": "Focus on compounds"  // NEW - optional, string
}
```

#### Session model

Sessions get a `status` field, `planned_exercises` array, and `failed` bool on exercises:

```jsonc
{
  "id": "s-uuid",                  // NEW - stable identifier for updates
  "date": "2026-04-07",
  "day": "Tuesday",
  "week": "W8",
  "week_number": 8,
  "phase": "Intensification II",   // CHANGED - string name (not nested dict)
  "block": "rebuild",
  "status": "completed",           // NEW - "planned" | "logged" | "completed" | "skipped"

  "planned_exercises": [           // NEW - the program design
    {"name": "Squat", "sets": 4, "reps": 3, "kg": 170},
    {"name": "Bench Press", "sets": 4, "reps": 3, "kg": 115},
    {"name": "Deadlift", "sets": 3, "reps": 2, "kg": 210}
  ],

  "exercises": [                   // RENAMED - this is now always actual work
    {"name": "Squat", "sets": 1, "reps": 3, "kg": 120, "failed": false, "notes": "warmup"},
    {"name": "Squat", "sets": 1, "reps": 3, "kg": 150, "failed": false, "notes": ""},
    {"name": "Squat", "sets": 1, "reps": 2, "kg": 170, "failed": true, "notes": "2nd rep grind"},
    {"name": "Bench Press", "sets": 1, "reps": 3, "kg": 115, "failed": false, "notes": "solid"}
  ],

  "session_rpe": 8,                // optional
  "body_weight_kg": 88.5,          // optional
  "session_notes": "...",
  "pain_log": [],
  "completed": true                // kept for backward compat
}
```

**Status lifecycle:**
- `planned` — session exists in the program with `planned_exercises` but no actual work logged
- `logged` — some actual exercises have been recorded
- `completed` — all planned exercises have been performed (or the user marks it done)
- `skipped` — the session was planned but never performed

#### Glossary exercise enrichment

Each exercise in the glossary gains a mandatory `fatigue_category` field:

```jsonc
{
  "id": "squat-001",
  "name": "Squat",
  "muscle_groups": ["quads", "glutes", "core"],
  "fatigue_category": "primary_axial",  // NEW - mandatory, defaults to "accessory"
  // ... existing fields
}
```

**Fatigue categories and multipliers:**

| Category | Fatigue Multiplier | Description |
|---|---|---|
| `primary_axial` | 1.0 | Squat, deadlift, and variations with significant axial loading |
| `primary_upper` | 0.8 | Bench press, OHP, and heavy upper body compounds |
| `secondary` | 0.6 | Close variations (pause bench, RDL, front squat, block pull) |
| `accessory` | 0.3 | Everything else — leg press, rows, curls, extensions. **Default** |

The glossary editor UI gains a dropdown for fatigue_category with these four options, defaulting to `accessory`.

#### current_maxes auto-population

The `current_maxes` field in the program root should be populated automatically:
- Priority: manually set values > most recent competition results > estimated from sessions
- Updated whenever a session is logged or a competition is completed

---

## Analytics Algorithms

All algorithms operate only on actual performed data (sessions with exercises logged, non-failed sets). RPE is used when available but never required.

### 1. Session Compliance

```
planned_sessions = sessions where status in ("planned", "logged", "completed", "skipped") within date window
completed_sessions = sessions where status in ("logged", "completed") within date window
compliance_pct = completed_sessions / planned_sessions * 100
```

### 2. Current Max Estimation

For each main lift (squat, bench, deadlift), find the best set in the last 30 days:

```
For each completed non-failed set of the lift:
  if session_rpe is logged for that set:
    %1rm = RPE_TABLE[reps][rpe]
    e1rm = kg / %1rm
  else:
    e1rm = kg * (1 + reps / 30)   // Epley formula

current_max[lift] = max(e1rm across all qualifying sets)
```

Override hierarchy: manual > competition results > session estimates.

### 3. DOTS Score Estimation

```
estimated_total = current_max["squat"] + current_max["bench"] + current_max["deadlift"]
estimated_dots = calculate_dots(estimated_total, body_weight_kg, sex)
```

Uses the existing DOTS coefficients. Shows both current estimated DOTS and projected competition DOTS.

### 4. Progression Rate

```
For each main lift:
  points = [(week_index, top_set_kg) for each session where:
    - session is completed
    - exercise matches the lift name
    - set is not failed
    - top_set_kg is the heaviest set in that session]

  slope, intercept, r2 = OLS(points)
  slope_kg_per_week = slope
```

### 5. Volume Tracking (per exercise, with fatigue category)

```
exercise_volume = sets * reps * kg
exercise_fatigue_load = exercise_volume * (kg / estimated_1rm) * fatigue_multiplier(fatigue_category)
session_fatigue_load = sum of exercise_fatigue_loads
weekly_fatigue_load = sum of session_fatigue_loads for that training week
```

### 6. Fatigue / Overreaching Signal

No RPE required. Derived from observable training data:

```
fatigue_score =
  0.40 * clamp(failed_compound_sets / total_compound_sets_last_14_days, 0, 1)
+ 0.35 * clamp(fatigue_load_spike, 0, 1)    // (this_week - avg_prev_3_weeks) / avg_prev_3_weeks
+ 0.25 * clamp(skipped_sessions / planned_sessions_last_14_days, 0, 1)

Flags:
  "failed_sets_spike"   if failed_compound_ratio > 0.15
  "volume_spike"        if fatigue_load increased > 20% week-over-week
  "skipping_sessions"   if skip_rate > 30%
  "overreaching_risk"   if fatigue_score >= 0.6
```

Where `compound_sets` = sets from exercises with fatigue_category in (primary_axial, primary_upper, secondary).

### 7. Meet Projection

```
For each lift:
  current_kg = current_max[lift]
  slope = progression_rate[lift].slope_kg_per_week
  projected = current_kg + slope * min(weeks_to_comp, 12)
  projected = max(projected, current_kg)  // never project below current

projected_total = sum of projected lifts
projected_dots = calculate_dots(projected_total, target_bodyweight, sex)
```

### 8. Per-Lift Breakdown

Shows for each main lift in the analysis window:
- Progression rate (kg/week) with R² confidence
- Week-over-week volume change %
- Week-over-week intensity (top set kg) change %
- Failed set count
- RPE trend (if any RPE data exists for this lift — optional column)

**Bug fix:** The per-lift breakdown table must respect the selected week dropdown filter. Currently it appears to always show the same data regardless of the selected time range.

---

## Migration Script

Standalone Python script (`scripts/migrate_program_schema.py`) that:

1. Reads the current program version (via pointer or latest)
2. For each session:
   - Sets `status` based on `completed` field: `true` → `"completed"`, `false` → `"planned"`
   - Converts `phase` from dict to string name: `phase.get("name", "")`
   - Adds `failed: false` to all exercises
   - Adds empty `planned_exercises: []`
   - Generates stable `id` if missing (UUID from date+index)
3. For each phase: adds empty `target_rpe_min`, `target_rpe_max`, `days_per_week`, `notes` fields
4. For each glossary exercise: adds `fatigue_category` field, auto-classified by name matching (squat/deadlift variations → `primary_axial`, bench/OHP → `primary_upper`, known secondaries → `secondary`, rest → `accessory`)
5. Populates `current_maxes` from most recent competition results
6. Writes as new program version and updates pointer
7. Idempotent — safe to re-run

---

## UI Pages

### A. Program Designer (`/app/fitness/designer`)

**New page.** Phase-based layout for building sessions ahead of time.

Layout:
- **Left sidebar:** Phase list (name + week range). Click to select. Button to add/edit/delete phases.
- **Main area:** Week selector dropdown. Shows sessions for the selected week as cards.
- **Session card:** Shows date, day, planned exercises with target sets/reps/kg. Click to edit.
- **Session editor (modal/drawer):**
  - Date, day, phase assignment
  - Exercise list with target sets/reps/kg per exercise
  - Add exercises from glossary (search/autocomplete)
  - Save populates `planned_exercises` and creates session with `status: "planned"`
- **Phase editor (modal):** Name, start/end week, intent, target RPE range, days/week, notes

### B. Glossary Editor (existing page — add fatigue_category)

Add a dropdown to each exercise in the glossary:
- Label: "Fatigue Category"
- Options: Primary Axial, Primary Upper, Secondary, Accessory
- Default: Accessory
- Required field

### C. Analysis Page (`/app/fitness/analysis` — modified)

Cards layout (top row):
1. **Current Maxes** — estimated 1RM per lift + estimated DOTS at current bodyweight. Shows method label (comp/session/RPE). Card shows 3 lifts side by side.
2. **Compliance** — planned vs completed sessions. Shows planned count, completed count, percentage. Phase name underneath.
3. **Fatigue Signal** — compound load-based score 0-100%. Description text: "Based on failed compound sets (40%), fatigue load spike (35%), and session skip rate (25%)." Color-coded (green/yellow/red).
4. **Meet Projection** — projected total kg + projected DOTS. Weeks to competition. Method label. If no projection possible, shows the actual reason (not hardcoded "no competition date set").

Tables:
- **Per-Lift Breakdown** — respects week dropdown filter. Shows progression, volume change, intensity change, failed sets per lift.
- **Volume Trend** (new) — weekly fatigue load chart showing compound vs total volume over time.

---

## Files to Modify

### Python backend (app/src/)
| File | Change |
|---|---|
| `health/analytics.py` | Rewrite all algorithms per this spec |
| `health/export.py` | Update export to use planned/actual, fatigue_category, new session structure |
| `api/health_analytics.py` | Update API responses to match new schema |
| `health/tools.py` | Add `failed` field handling, `planned_exercises` support |

### Node.js backend (utils/powerlifting-app/backend/src/)
| File | Change |
|---|---|
| `server.ts` | Add routes for program designer CRUD |
| `routes/programs.ts` | Add endpoints: create planned session, update planned exercises, batch-create week |
| `routes/sessions.ts` | Update to handle `status`, `planned_exercises`, `failed` fields |
| `routes/exercises.ts` | Add `fatigue_category` field to glossary CRUD |

### Frontend (utils/powerlifting-app/frontend/src/)
| File | Change |
|---|---|
| `pages/DesignerPage.tsx` | NEW — program designer page |
| `pages/AnalysisPage.tsx` | REWRITE — new cards, new metrics, fixed week filter |
| `pages/GlossaryPage.tsx` | Add fatigue_category dropdown |
| `api/client.ts` | Add API calls for designer CRUD |
| `api/analytics.ts` | Update types for new response schema |
| `components/layout/Sidebar.tsx` | Add Designer nav item |
| `App.tsx` | Add `/designer` route |

### Migration
| File | Change |
|---|---|
| `scripts/migrate_program_schema.py` | NEW — one-time migration script |

---

## Verification

1. **Migration:** Run migration script, verify all 139 sessions have status/failed/planned_exercises, phases have new fields, glossary has fatigue_category, current_maxes populated
2. **Analytics:** After migration, hit `/v1/health/analysis/weekly?weeks=4` — should return valid metrics without errors
3. **Export:** Hit `/v1/health/export/xlsx` — should produce valid Excel file
4. **Designer:** Create a planned session, verify it appears in the session list with `status: "planned"`
5. **Compliance:** After logging actual work against a planned session, verify compliance score reflects the change
6. **Per-lift table:** Switch between 1/2/4/8 week dropdowns, verify the per-lift breakdown data changes accordingly
7. **Build:** `npm run build` succeeds for both frontend and backend
