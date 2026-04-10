# Powerlifting Training Portal

A web application for managing powerlifting training programs, tracking progress, analyzing performance, and preparing for competitions.

## Tech Stack

- **Frontend:** React 18 + Vite, TypeScript, Tailwind CSS, Zustand (state), Recharts (charts)
- **Backend:** Node.js Express (API + DynamoDB CRUD), Python FastAPI (analytics engine)
- **Database:** DynamoDB single-table (`if-health`)
- **Deployment:** K3s Kubernetes, Tailscale Funnel ingress

## Running Locally

```bash
# Frontend (port 3005)
cd frontend && npm install && npm run dev

# Backend (port 3005 API)
cd backend && npm install && npm run dev
```

The frontend dev server proxies `/api/*` calls to the Express backend. The analytics endpoints further proxy to the Python FastAPI service at `IF_API_URL`.

## Pages

### Dashboard

Overview of current training status: current maxes (squat/bench/deadlift), estimated DOTS score, body weight vs weight class, current phase, target vs actual lifts, and phase progress.

### Designer

Visual program designer for planning training phases and sessions. Select a phase from the sidebar, navigate weeks, and plan individual sessions with exercises from the glossary. Block-scoped — only shows sessions for the selected block.

- Phase editor with name, intent, week range, target RPE range, days per week
- Session editor with date, day, week, phase, and planned exercises
- Exercises searchable from the glossary
- Block filter to isolate current vs archived training blocks

### Analysis

The core analytics page. Provides a comprehensive weekly analysis of training data using deterministic algorithms (no LLM — pure math via Python). Block-scoped and time-windowed.

**Summary Cards (4 across):**

| Card | Details |
|------|---------|
| **Current Maxes** | Squat/bench/deadlift estimated 1RM, estimation method (manual or session-derived), estimated DOTS score |
| **Compliance** | Planned vs completed sessions percentage, current phase name |
| **Fatigue Signal** | Composite fatigue index (0-100%) with components: failed compound sets ratio, fatigue load spike, session skip rate |
| **Projected Total** | Competition total projection using diminishing-returns formula, confidence %, weeks to competition, competition name |

**Body Weight Trend:**
- Current weight and change over the analysis window
- Recent weight entries (last 8 data points)

**Competitions Table:**
- All competitions listed with name, date, status (confirmed/optional/completed/skipped)
- Completed competitions show individual lift results (squat/bench/deadlift) and total

**Per-Lift Breakdown Table:**
- Progression rate (kg/week via OLS regression)
- R² fit quality
- Volume change %, intensity change %
- Failed sets count
- RPE trend (rising/stable/improving)

**Exercise Volume Table:**
- Per-exercise total sets, total volume (kg), and heaviest weight lifted
- Sorted by total volume descending

**Sets by Muscle Group:**
- Grid of muscle groups with total set count
- Uses glossary muscle group mapping (primary muscles count full, secondary count half)

**Sets by Fatigue Category:**
- Primary Axial, Primary Upper, Secondary, Accessory
- Total sets per category based on glossary fatigue_category field

**Flags:**
- Warning badges for detected issues (overreaching risk, volume spike, failed sets spike, RPE drift)

**Controls:**
- Time window selector (1/2/4/8 weeks)
- Block filter (if multiple blocks exist)
- Export to Excel

### Charts

Interactive charts for volume and intensity trends. Breakdown by lift category or muscle group. Weekly and all-time views. Block-scoped.

### Log

Session logging interface. Record exercises with sets, reps, weight, RPE. Mark sessions as complete with optional body weight and session notes. Video recording support.

### List

Chronological session list view with status indicators. Filter by block. Click to expand session details.

### Maxes

Max history tracking with timeline chart. Shows progression of squat/bench/deadlift 1RM estimates over time.

### Glossary

Exercise definition manager. Each exercise has:
- Name, category (squat/bench/deadlift/back/chest/arms/legs/core/lower_back)
- Equipment type (barbell/dumbbell/cable/machine/bodyweight/etc.)
- Fatigue category (primary_axial/primary_upper/secondary/accessory)
- Primary and secondary muscle groups
- Coaching cues
- Notes

Full CRUD with search.

## Data Model

| Entity | Key Fields | Storage |
|--------|-----------|---------|
| **Program** | `meta`, `phases`, `sessions`, `competitions`, `supplements`, `diet_notes` | DynamoDB `if-health` PK=`operator` SK=`program#v{N}` |
| **Session** | `date`, `day`, `week`, `week_number`, `block`, `phase`, `status`, `exercises`, `planned_exercises`, `body_weight_kg`, `session_rpe` | Nested in program |
| **Exercise** | `name`, `kg`, `sets`, `reps`, `rpe`, `failed` | Nested in session |
| **Phase** | `name`, `intent`, `start_week`, `end_week`, `target_rpe_min`, `target_rpe_max`, `days_per_week` | Nested in program |
| **Competition** | `name`, `date`, `federation`, `status`, `weight_class_kg`, `results`, `targets` | Nested in program |
| **GlossaryExercise** | `id`, `name`, `category`, `fatigue_category`, `primary_muscles`, `secondary_muscles`, `equipment`, `cues` | DynamoDB SK=`glossary#v1` |
| **Weight Log** | `entries: [{date, kg}]` | DynamoDB SK=`weight_log#{version}` |

## Analytics Pipeline

All analytics run in Python (`app/src/health/analytics.py`) — pure deterministic math, no LLM calls. Frontend-computed metrics use glossary joins and session data client-side.

### 1RM Estimation

Three formulas, applied per set where `failed = false`:

| Formula | Equation | Use Case |
|---------|----------|----------|
| **Epley** | `1RM = weight × (1 + reps / 30)` | Default when no RPE available |
| **Brzycki** | `1RM = weight × 36 / (37 - reps)` | Cross-check |
| **RPE Table** | `1RM = weight / pct` where `pct` from `(reps, rpe)` lookup table | Preferred when RPE is recorded (6-10 scale) |

The RPE table uses the Reactive Training Systems standard. Example entries: `(1, 10) → 1.000`, `(5, 8) → 0.815`, `(10, 7) → 0.695`.

**Session-derived max estimation:** Scans all completed sessions in the last 90 days. For each set of squat/bench/deadlift (exact name match), computes e1RM. Takes the highest e1RM per lift. Requires at least 2 of the 3 lifts to return a result.

### DOTS Score

Polynomial coefficient formula, normalized to bodyweight:

```
DOTS = (500 / denominator) × total_kg

denominator = a + b×bw + c×bw² + d×bw³ + e×bw⁴
```

Coefficients:

| | Male | Female |
|---|------|--------|
| a | -307.75076 | -57.96288 |
| b | 24.0900756 | 13.6175032 |
| c | -0.1918759221 | -0.1126655495 |
| d | 0.0007391293 | 0.0005158568 |
| e | -0.000001093 | -0.0000010706 |

### Progression Rate

Ordinary Least Squares (OLS) regression on top-set weights over time:

```
For each completed session containing exercise X:
  week_index = (session_date - program_start) / 7

OLS on (week_index, top_kg) pairs:
  slope = kg gained per week
  r² = goodness of fit
```

Requires at least 2 data points. Returns `slope_kg_per_week` and `r_squared`.

### Fatigue Index

Composite score from three observable components, no RPE required:

```
fatigue_index = 0.40 × failed_compound_ratio + 0.35 × load_spike + 0.25 × skip_rate
```

| Component | Weight | Calculation |
|-----------|--------|-------------|
| Failed compound sets ratio | 40% | `failed_compound_sets / total_compound_sets` (compounds = exercises containing squat/deadlift/bench/press/row/rdl/pullup/chinup) |
| Fatigue load spike | 35% | `clamp((this_week_volume - avg_prev_3_weeks_volume) / avg_prev_3_weeks_volume, 0, 1)` |
| Session skip rate | 25% | `skipped_sessions / total_planned_sessions` in the analysis window |

**Flag thresholds:**
- `failed_sets_spike` when failed_compound_ratio > 0.15
- `volume_spike` when load_spike > 0.20
- `skipping_sessions` when skip_rate > 0.30
- `overreaching_risk` when fatigue_index >= 0.60

**Fatigue categories with multipliers:**
- Primary Axial: 1.0 (squat, deadlift)
- Primary Upper: 0.8 (bench press)
- Secondary: 0.6 (pause squats, close-grip bench)
- Accessory: 0.3 (leg extensions, curls)

### Meet Projection

Diminishing-returns exponential model with DOTS-based decay:

```
C_max = [E_now + Δw × λ × (1 - λ^n_t) / (1 - λ)] × P
```

Where:
- `E_now` = current estimated 1RM from session data
- `Δw` = weekly progression rate (slope from OLS regression)
- `λ` = decay parameter based on DOTS level
- `n_t` = weeks remaining minus taper weeks
- `P` = peaking factor based on DOTS level

**Lambda (λ) by DOTS level:**

| DOTS | Level | λ | Peaking Factor |
|------|-------|---|----------------|
| < 300 | Beginner | 0.96 | 1.01 |
| 300-400 | Intermediate | 0.90 | 1.03 |
| ≥ 400 | Advanced | 0.85 | 1.05 |

**Taper weeks by time remaining:**

| Weeks to comp | Taper weeks |
|---------------|-------------|
| ≥ 12 | 3 |
| 8-11 | 2 |
| < 8 | 1 |

Projection never goes below current max. Finds next + final upcoming competition in the current block.

### RPE Drift Detection

OLS regression on (week_index, avg_rpe) for each exercise:

```
slope >= 0.1  → "up" (fatigue flag)
slope <= -0.1 → "down" (adaptation)
otherwise     → "stable"
```

Requires at least 3 RPE data points. Falls back to exercise-level RPE when session RPE is unavailable.

### Compliance

```
compliance_pct = completed_sessions / planned_sessions × 100
```

Counts sessions with status `logged` or `completed` as completed. Planned = all sessions with status `planned`, `logged`, `completed`, or `skipped`.

### Per-Lift Details (Frontend)

Computed client-side using glossary + session data for the current block:

| Metric | Formula |
|--------|---------|
| **Frequency** | `sessions_containing_lift / distinct_weeks` — how many sessions per week include the main lift |
| **Raw Sets** | Sum of `sets` for the exact lift name across all completed sessions in the block |
| **Accessory Work** | Exercises where `glossary.category === lift_category` AND `glossary.fatigue_category IN (secondary, accessory)`. Aggregates sets and volume (sets × reps × kg) |

Category mapping: squat → `squat`, bench → `bench`, deadlift → `deadlift`.

### Muscle Group Aggregation (Frontend)

Uses glossary muscle group mapping:

```
For each exercise in completed sessions (current block):
  For each primary muscle:    total += sets (or sets × reps × kg for volume)
  For each secondary muscle:  total += sets × 0.5 (or volume × 0.5)
```

**Avg weekly:** `total / distinct_weeks` where distinct_weeks = number of unique week_number values in filtered sessions.

### Avg Sessions Per Week

```
avg_sessions_per_week = sessions_analyzed / weeks_in_window
```

### Nutrition Trend (Frontend)

Aggregates diet notes within the analysis window:

```
avg_calories = SUM(avg_daily_calories) / COUNT(notes with calories)
avg_water    = SUM(water_intake) / COUNT(notes with water)
consistency  = COUNT(consistent=true) / COUNT(all notes) × 100
```
