# Plan 5: New Metrics - INOL, ACWR, RI Distribution, Specificity, Readiness (Sections 8-12)

## Context
Plans 1-4 fixed the foundation and dependent metrics. This plan adds 5 entirely new metrics and wires them into the analytics response and frontend.

## Files to Modify
- `app/src/health/analytics.py` — add 5 new public functions
- `app/src/api/health_analytics.py` — pass glossary to weekly_analysis
- `utils/powerlifting-app/frontend/src/api/analytics.ts` — extend WeeklyAnalysis interface
- `utils/powerlifting-app/frontend/src/pages/AnalysisPage.tsx` — add new card sections

## Step 1: Add INOL Metric (Section 8)

**File:** `app/src/health/analytics.py`

### 1a. New function `compute_inol()`
```python
def compute_inol(
    sessions: list[dict],
    program_start: str = "",
    current_maxes: dict | None = None,
) -> dict:
    """INOL per main lift per week: sum(reps / (100 * (1 - I))) where I = weight / E_now."""
```

Logic:
1. If no `current_maxes` provided, estimate from sessions
2. For each completed session containing a main lift (squat/bench/deadlift):
   - For each set of that lift:
     - `I = weight / current_maxes[lift]`
     - Guard: if `I >= 1.0`, cap denominator: use `max(0.01, 1 - I)`
     - `inol_contribution = reps / (100 * (1 - I))`
   - Aggregate by week and lift
3. Return:
```python
{
    "per_lift_per_week": {
        "squat": {1: 1.2, 2: 1.5, ...},
        "bench": {1: 0.8, 2: 1.1, ...},
        "deadlift": {1: 0.9, 2: 1.3, ...},
    },
    "current_week": {
        "squat": 1.5,
        "bench": 1.1,
        "deadlift": 1.3,
    },
    "flags": ["low_stimulus_squat"] if any < 2.0, ["overreaching_deadlift"] if any > 4.0
}
```

Flag logic:
- INOL < 2.0 → "low_stimulus_{lift}"
- INOL 2.0-4.0 → "productive" (no flag)
- INOL > 4.0 → "overreaching_risk_{lift}"

### 1b. Add to `weekly_analysis()` return
```python
"inol": compute_inol(filtered_sessions, program_start, current_maxes)
```

## Step 2: Add ACWR Metric (Section 9)

**File:** `app/src/health/analytics.py`

### 2a. New function `compute_acwr()`
```python
def compute_acwr(
    sessions: list[dict],
    glossary: list[dict] | None = None,
    program_start: str = "",
    current_maxes: dict | None = None,
) -> dict:
    """Acute:Chronic Workload Ratio - per dimension and composite."""
```

Logic:
1. Compute weekly fatigue by dimension using `_weekly_fatigue_by_dimension()` (from Plan 2)
2. Detect deloads using `_detect_deloads()`
3. Compute per-dimension ACWR using `_compute_dimensional_acwr()` (from Plan 2)
4. Apply zone classification per dimension and composite:
   - < 0.8 → "undertraining"
   - 0.8-1.3 → "optimal"
   - 1.3-1.5 → "caution"
   - > 1.5 → "danger"
5. Return:
```python
{
    "composite": float,
    "composite_zone": str,
    "dimensions": {
        "axial": {"value": float, "zone": str},
        "neural": {"value": float, "zone": str},
        "peripheral": {"value": float, "zone": str},
        "systemic": {"value": float, "zone": str},
    },
}
```

### 2b. Add to `weekly_analysis()` return
```python
"acwr": compute_acwr(filtered_sessions, glossary, program_start, current_maxes)
```

## Step 3: Add Relative Intensity Distribution (Section 10)

**File:** `app/src/health/analytics.py`

### 3a. New function `compute_ri_distribution()`
```python
def compute_ri_distribution(
    sessions: list[dict],
    current_maxes: dict | None = None,
) -> dict:
    """Bucket working sets by relative intensity: heavy (>0.85), moderate (0.70-0.85), light (<0.70)."""
```

Logic:
1. If no `current_maxes`, return `INSUFFICIENT_DATA`
2. For each completed session, for each exercise matching a main lift:
   - `RI = weight / current_maxes[lift]`
   - Classify: heavy (>0.85), moderate (0.70-0.85), light (<0.70)
3. Count and compute percentages per bucket, both overall and per-lift
4. Return:
```python
{
    "overall": {
        "heavy": {"count": 12, "pct": 30.0},
        "moderate": {"count": 20, "pct": 50.0},
        "light": {"count": 8, "pct": 20.0},
    },
    "per_lift": {
        "squat": {"heavy": ..., "moderate": ..., "light": ...},
        "bench": ...,
        "deadlift": ...,
    },
}
```

### 3b. Add to `weekly_analysis()` return
```python
"ri_distribution": compute_ri_distribution(filtered_sessions, current_maxes)
```

## Step 4: Add Specificity Ratio (Section 11)

**File:** `app/src/health/analytics.py`

### 4a. New function `compute_specificity_ratio()`
```python
def compute_specificity_ratio(
    sessions: list[dict],
    glossary: list[dict] | None = None,
) -> dict:
    """SR_narrow = SBD sets / total sets; SR_broad = (SBD + secondary) / total sets."""
```

Logic:
1. Count total working sets across all completed sessions in the window
2. Count SBD sets: exercises where name matches "squat", "bench press", "bench", "deadlift" (exact match, case-insensitive)
3. For SR_broad: if glossary available, also count exercises whose glossary `category` matches "squat", "bench", or "deadlift"
4. Compute ratios:
   - `SR_narrow = SBD_sets / total_sets`
   - `SR_broad = broad_sets / total_sets`
5. Return:
```python
{
    "narrow": float,  # 0.0-1.0
    "broad": float,   # 0.0-1.0
    "total_sets": int,
    "sbd_sets": int,
    "secondary_sets": int,
}
```

### 4b. Add to `weekly_analysis()` return
```python
"specificity_ratio": compute_specificity_ratio(filtered_sessions, glossary)
```

## Step 5: Add Readiness Score (Section 12)

**File:** `app/src/health/analytics.py`

### 5a. New function `compute_readiness_score()`
```python
def compute_readiness_score(
    sessions: list[dict],
    program: dict,
    glossary: list[dict] | None = None,
    program_start: str = "",
) -> dict:
    """R = (1 - (0.30*F_norm + 0.25*D_rpe + 0.20*S_bw + 0.15*M_rate + 0.10*(1-C_pct/100))) * 100"""
```

Components:
- `F_norm`: fatigue_index / 100 (from updated `fatigue_index()`)
- `D_rpe`: `clamp((avg_rpe_last_2wk - phase_target_rpe_midpoint) / 2, 0, 1)`
- `S_bw`: `clamp(CV(last 7 bodyweight entries) / 0.03, 0, 1)` — coefficient of variation
- `M_rate`: `failed_sets / total_sets` over last 2 weeks
- `C_pct`: compliance percentage (from updated `session_compliance()`)

Return:
```python
{
    "score": float,  # 0-100
    "zone": str,     # "green" > 75, "yellow" 50-75, "red" < 50
    "components": {
        "fatigue_norm": float,
        "rpe_drift": float,
        "bw_stability": float,
        "miss_rate": float,
        "compliance_pct": float,
    },
}
```

### 5b. Add to `weekly_analysis()` return
```python
"readiness_score": compute_readiness_score(filtered_sessions, program, glossary, program_start)
```

## Step 6: Ensure API Endpoint Passes Glossary

**File:** `app/src/api/health_analytics.py`

This was done in Plan 2 Step 7, but verify: the `get_weekly_analysis` endpoint fetches the glossary and passes it to `weekly_analysis()`. If not done yet, do it now.

## Step 7: Update Frontend Types

**File:** `utils/powerlifting-app/frontend/src/api/analytics.ts`

Add all new optional fields to `WeeklyAnalysis`:
```typescript
export interface WeeklyAnalysis {
  // ... existing fields unchanged ...

  // New metrics (all optional for backward compat)
  deload_info?: {
    deload_weeks: number[]
    break_weeks: number[]
    effective_training_weeks: number
  }
  inol?: {
    per_lift_per_week: Record<string, Record<string, number>>
    current_week: Record<string, number>
    flags: string[]
  }
  acwr?: {
    composite: number
    composite_zone: string
    dimensions: Record<string, { value: number; zone: string }>
  }
  ri_distribution?: {
    overall: Record<string, { count: number; pct: number }>
    per_lift: Record<string, Record<string, { count: number; pct: number }>>
  }
  specificity_ratio?: {
    narrow: number
    broad: number
    total_sets: number
    sbd_sets: number
  }
  readiness_score?: {
    score: number
    zone: string
    components: Record<string, number>
  }
  fatigue_dimensions?: {
    weekly: Record<string, { axial: number; neural: number; peripheral: number; systemic: number }>
    acwr: Record<string, any>
    spike: Record<string, any>
  }
}
```

## Step 8: Add Frontend Card Sections

**File:** `utils/powerlifting-app/frontend/src/pages/AnalysisPage.tsx`

Add new card sections in the analysis page. Place them after the existing top summary cards and projection tiles, before the per-lift breakdown table.

### 8a. Readiness Score card (top summary row)
- Add as 4th card in the top summary grid (alongside Maxes, Compliance, Fatigue)
- Circular or bar progress indicator
- Color: green > 75, yellow 50-75, red < 50
- Show score as large number with zone label

### 8b. INOL section
- Bar chart (Recharts BarChart) showing INOL per lift for the current week
- Color code: green (2.0-4.0), yellow (< 2.0), red (> 4.0)
- Show flag messages if any

### 8c. ACWR section
- Display composite ACWR with zone badge
- Show 4 dimension values in a row with zone colors
- Flag any dimensions in "caution" or "danger" zone

### 8d. Relative Intensity Distribution section
- Pie chart or horizontal stacked bar showing heavy/moderate/light split
- Show per-lift breakdown in a sub-table

### 8e. Specificity Ratio section
- Two progress bars (narrow and broad) showing percentage
- Display raw set counts alongside

### 8f. Fatigue Dimensions section
- 4-line chart or stacked bar showing weekly fatigue by dimension
- Flag "Neural overload" and "Axial overload" if ACWR > 1.3

Each section should only render if the corresponding data key exists in the API response (graceful degradation).

## Verification
- Run the app
- Hit `GET /v1/health/analysis/weekly?weeks=4` and verify all new keys present with correct shapes
- Verify existing keys unchanged
- `npm run build` in both `frontend/` and `backend/`
- Verify the analysis page renders without errors, including new card sections
