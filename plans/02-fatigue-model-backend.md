# Plan 2: Fatigue Model Overhaul - Backend (Section 4 backend parts)

## Context
The current fatigue model uses a single `fatigue_category` enum with one scalar multiplier. This is too coarse — a squat produces axial, neural, peripheral, AND systemic fatigue simultaneously. This plan adds 4-dimensional fatigue profiles, an AI estimation endpoint, and deterministic fatigue math functions. Frontend changes come in Plan 3.

## Files to Modify
- `utils/powerlifting-app/packages/types/index.ts` — add FatigueProfile interface
- `app/src/health/analytics.py` — add deterministic fatigue calculation functions
- `app/src/health/fatigue_ai.py` (NEW) — LLM-based fatigue profile estimation
- `app/src/api/health_analytics.py` — add POST endpoint

## Step 1: Update TypeScript Types

**File:** `utils/powerlifting-app/packages/types/index.ts`

Add new interface after the `FatigueCategory` type (~line 247):

```typescript
export interface FatigueProfile {
  axial: number       // 0.0-1.0, spinal compression loading
  neural: number      // 0.0-1.0, CNS demand baseline
  peripheral: number  // 0.0-1.0, local muscle damage potential
  systemic: number    // 0.0-1.0, cardiovascular/metabolic demand
}

export type FatigueProfileSource = 'ai_estimated' | 'manual'
```

Extend `GlossaryExercise` interface (~line 249):
```typescript
export interface GlossaryExercise {
  // ... existing fields unchanged ...
  fatigue_profile?: FatigueProfile
  fatigue_profile_source?: FatigueProfileSource
  fatigue_profile_reasoning?: string | null
}
```

These are all optional fields — existing exercises without them continue to work.

## Step 2: Add Fallback Default to analytics.py

**File:** `app/src/health/analytics.py`

Add constant near the top (after removing FATIGUE_MULTIPLIERS in Plan 1, or alongside existing constants):

```python
# Safe neutral fallback for exercises without a fatigue profile.
# Deliberately mediocre — motivates getting a real estimate.
_DEFAULT_FATIGUE_PROFILE = {
    "axial": 0.3,
    "neural": 0.3,
    "peripheral": 0.5,
    "systemic": 0.3,
}
```

## Step 3: Add Deterministic Fatigue Functions to analytics.py

Add these functions in a new section (after the existing helpers, before the public API functions):

### 3a. `_get_fatigue_profile(exercise_name, glossary) -> dict`

```python
def _get_fatigue_profile(
    exercise_name: str,
    glossary: list[dict] | None = None,
) -> dict:
    """Look up fatigue profile from glossary. Falls back to _DEFAULT_FATIGUE_PROFILE."""
```

Logic:
1. If glossary is provided, search for exercise by name match (case-insensitive)
2. If found and has `fatigue_profile` dict with all 4 keys: return it
3. Else: log a warning (`logger.warning(f"No fatigue profile for {exercise_name}")`) and return `_DEFAULT_FATIGUE_PROFILE`

### 3b. `_neural_scaling(relative_intensity) -> float`

```python
def _neural_scaling(I: float) -> float:
    """phi(I) = (max(0, I - 0.60) / 0.40)^2"""
```

Values: I<=60% → 0.00, I=70% → 0.0625, I=80% → 0.25, I=90% → 0.5625, I=100% → 1.00

### 3c. `_per_set_fatigue(weight, reps, profile, e1rm=None) -> dict`

```python
def _per_set_fatigue(
    weight: float,
    reps: int,
    profile: dict,
    e1rm: float | None = None,
) -> dict:
    """Compute per-set fatigue across 4 dimensions."""
```

Formulas from the spec:
```
I = weight / e1rm if e1rm else 0.70  (fallback for non-main lifts)
F_axial      = profile.axial * weight * reps
F_neural     = profile.neural * reps * phi(I)
F_peripheral = profile.peripheral * weight * reps
F_systemic   = profile.systemic * weight * reps
```

Return `{"axial": F_axial, "neural": F_neural, "peripheral": F_peripheral, "systemic": F_systemic}`

### 3d. `_weekly_fatigue_by_dimension(sessions, glossary, program_start, current_maxes) -> dict`

```python
def _weekly_fatigue_by_dimension(
    sessions: list[dict],
    glossary: list[dict] | None,
    program_start: str,
    current_maxes: dict,
) -> dict[float, dict[str, float]]:
    """Sum per-set fatigue into weekly totals per dimension.
    Returns {week_index: {axial: X, neural: Y, peripheral: Z, systemic: W}}"""
```

Logic:
1. For each completed session, for each exercise, for each set (sets count):
   - Look up fatigue profile via `_get_fatigue_profile(exercise_name, glossary)`
   - Look up e1rm for main lifts from `current_maxes` (None for accessories)
   - Compute `_per_set_fatigue(weight, reps, profile, e1rm)`
   - Multiply by number of sets
   - Accumulate into weekly buckets

### 3e. `_compute_dimensional_acwr(weekly_fatigue, deload_info, acute_weeks=1, chronic_weeks=4) -> dict`

```python
def _compute_dimensional_acwr(
    weekly_fatigue: dict[float, dict[str, float]],
    deload_weeks: list[float],
    acute_weeks: int = 1,
    chronic_weeks: int = 4,
) -> dict:
    """Per-dimension ACWR + composite."""
```

Logic:
1. Exclude deload weeks from both acute and chronic windows
2. For each dimension d:
   - `ACWR_d = F_d_current_week / mean(F_d over previous chronic_weeks non-deload weeks)`
3. Composite: `0.30*ACWR_a + 0.30*ACWR_n + 0.25*ACWR_p + 0.15*ACWR_s`

### 3f. `_compute_dimensional_spike(weekly_fatigue, deload_weeks) -> dict`

```python
def _compute_dimensional_spike(
    weekly_fatigue: dict[float, dict[str, float]],
    deload_weeks: list[float],
) -> dict:
    """Per-dimension spike + composite."""
```

Logic:
1. For each dimension d:
   - `spike_d = clamp((F_d_week - mean(F_d prev 3 non-deload weeks)) / mean(F_d prev 3 non-deload weeks), 0, 1)`
2. Composite: same weights as ACWR

## Step 4: Create `fatigue_ai.py`

**New file:** `app/src/health/fatigue_ai.py`

This is separate from analytics.py because it makes LLM calls.

### 4a. Determine how to call the LLM

Check how the existing app calls OpenRouter. The project uses OpenRouter via `LLM_BASE_URL` (default `https://openrouter.ai/api/v1`) with `OPENROUTER_API_KEY`. Look at:
- `app/src/api/completions.py` for the existing chat completions flow
- `app/src/config.py` for `LLM_BASE_URL`, `OPENROUTER_API_KEY`

The simplest approach: make a direct HTTP POST to OpenRouter using `httpx` (should be in deps already since the app uses it). Use a cheap fast model like the router model (`MODEL_ROUTER_MODEL` config, default `google/gemma-3-4b-it`).

### 4b. Implement `estimate_fatigue_profile()`

```python
async def estimate_fatigue_profile(exercise: dict) -> dict:
    """Call LLM to estimate 4-dimensional fatigue profile for an exercise."""
```

Implementation:
1. Build system prompt from spec (section 4c) — the calibration anchors, dimension definitions, rules
2. Build user message from exercise fields (name, category, equipment, muscles, cues, notes)
3. Define the tool schema (`estimate_fatigue_profile` with axial/neural/peripheral/systemic/reasoning params)
4. POST to OpenRouter with `tools` parameter using tool calling
5. Parse the tool call response, extract values
6. Round all values to nearest 0.05
7. Return `{"axial": float, "neural": float, "peripheral": float, "systemic": float, "reasoning": str}`
8. On any failure: return `_DEFAULT_FATIGUE_PROFILE` with `"reasoning": "AI estimation failed"`

Use `httpx.AsyncClient` for the HTTP call. Read the API key from `config.py`.

## Step 5: Add POST API Endpoint

**File:** `app/src/api/health_analytics.py`

Add a new endpoint:

```python
@router.post("/fatigue-profile/estimate")
async def estimate_fatigue_profile_endpoint(request: dict):
    """Estimate fatigue profile for an exercise using AI."""
    from health.fatigue_ai import estimate_fatigue_profile
    result = await estimate_fatigue_profile(request)
    return result
```

The request body is the exercise dict with fields: name, category, equipment, primary_muscles, secondary_muscles, cues, notes.

## Step 6: Add fatigue data to `weekly_analysis()` return

Update `weekly_analysis()` signature to accept optional `glossary` parameter:

```python
def weekly_analysis(program, sessions, ref_date=None, weeks=1, block=None, glossary=None):
```

Call `_weekly_fatigue_by_dimension()` and add to return dict:
```python
"fatigue_dimensions": {
    "weekly": {week_index: {axial, neural, peripheral, systemic}},
    "acwr": {...},           # from _compute_dimensional_acwr
    "spike": {...},          # from _compute_dimensional_spike
    "dimension_weights": {"axial": 0.30, "neural": 0.30, "peripheral": 0.25, "systemic": 0.15},
}
```

## Step 7: Update API endpoint to fetch glossary

**File:** `app/src/api/health_analytics.py`

In the `get_weekly_analysis` endpoint, after fetching the program from DynamoDB, also fetch the glossary:

```python
from health.program_store import ProgramStore
glossary = await store.get_glossary()  # or equivalent DynamoDB fetch
result = weekly_analysis(program, sessions, weeks=weeks, block=block, glossary=glossary)
```

Check how the glossary is stored (DynamoDB item at `pk="operator"`, `sk="glossary#v1"`) and fetch it similarly to how the program is fetched.

## Verification
- Run the app
- Hit `POST /v1/health/fatigue-profile/estimate` with a sample exercise, verify 4-dimensional response
- Hit `GET /v1/health/analysis/weekly?weeks=4`, verify `fatigue_dimensions` key present
- Verify existing response keys unchanged
- Check `npm run build` in `packages/types` to confirm types compile
