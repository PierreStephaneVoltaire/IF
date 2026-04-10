# Plan 3: Fatigue Model - Frontend + Save Hook + Backfill (Section 4 frontend parts)

## Context
Plan 2 added the backend for 4-dimensional fatigue profiles. This plan wires it into the frontend glossary editor, adds the automatic AI estimation save hook, creates the backfill script, and adds the Node proxy route.

## Files to Modify
- `utils/powerlifting-app/frontend/src/pages/GlossaryPage.tsx` — add fatigue profile sliders
- `utils/powerlifting-app/backend/src/controllers/exerciseController.ts` — add save hook
- `utils/powerlifting-app/backend/src/routes/analytics.ts` — proxy new endpoint
- `scripts/backfill_fatigue_profiles.py` (NEW) — backfill script

## Step 1: Add Fatigue Profile Sliders to Glossary Editor

**File:** `utils/powerlifting-app/frontend/src/pages/GlossaryPage.tsx`

### 1a. Import Radix UI Slider

```typescript
import * as Slider from '@radix-ui/react-slider'
```

(Radix slider is already installed as a dependency: `@radix-ui/react-slider@^1.0.0`)

### 1b. Add profile state to form data

Extend the exercise form state to include:
```typescript
fatigue_profile: {
  axial: number      // 0-100 (displayed as 0.0-1.0, stored as 0-100 for slider)
  neural: number
  peripheral: number
  systemic: number
} | null
fatigue_profile_source: 'ai_estimated' | 'manual' | null
fatigue_profile_reasoning: string | null
```

### 1c. Add slider section in the exercise edit form

After the existing `fatigue_category` dropdown, add:

**Four sliders** (0.0 to 1.0, step 0.05):
- "Axial (spinal loading)"
- "Neural (CNS demand)"
- "Peripheral (muscle damage)"
- "Systemic (metabolic load)"

Each slider:
- Radix Slider with `min={0}`, `max={100}`, `step={5}` (internal 0-100, display as 0.0-1.0)
- Label with current value displayed as decimal (e.g. "0.75")
- Styled with Tailwind to match existing form controls

**Source badge**: below the sliders
- "AI estimated" (blue badge) or "Manual override" (green badge)
- If `source === 'ai_estimated'`, show `fatigue_profile_reasoning` as subtitle below badge

**Behavior**:
- If user changes ANY slider value → set source to `"manual"`, clear reasoning
- Show the section only when editing an existing exercise or creating new (always visible)

**"Re-estimate" button**:
- Calls the AI estimation endpoint
- On success, updates all 4 slider values + sets source back to "ai_estimated" + stores reasoning
- Shows loading state during estimation

### 1d. Wire to save function

Update `handleSave()` to include `fatigue_profile`, `fatigue_profile_source`, `fatigue_profile_reasoning` in the exercise upsert payload.

## Step 2: Add Node Proxy Route

**File:** `utils/powerlifting-app/backend/src/routes/analytics.ts`

The existing file proxies analytics requests to the Python FastAPI service at `IF_API_URL`. Add a new route:

```typescript
router.post('/fatigue-profile/estimate', async (req, res) => {
  // Proxy to POST {IF_API_URL}/v1/health/fatigue-profile/estimate
  // Forward request body, return response
})
```

Follow the same pattern as the existing `GET /analysis/weekly` proxy.

## Step 3: Add Save Hook to Exercise Controller

**File:** `utils/powerlifting-app/backend/src/controllers/exerciseController.ts`

In the `upsertExercise` function, after the DynamoDB write succeeds:

1. Check if `exercise.fatigue_profile` is missing/null AND `exercise.fatigue_profile_source !== 'manual'`
2. If so, make an async POST to `/api/analytics/fatigue-profile/estimate` (the Node proxy from Step 2) with the exercise fields
3. On success, update the exercise in DynamoDB with the returned profile:
   - Set `fatigue_profile` to the returned {axial, neural, peripheral, systemic}
   - Set `fatigue_profile_source` to `"ai_estimated"`
   - Set `fatigue_profile_reasoning` to the returned reasoning string
4. Fire-and-forget (don't block the response to the frontend)

```typescript
// After successful DynamoDB write
if (!exercise.fatigue_profile || exercise.fatigue_profile_source !== 'manual') {
  // Fire-and-forget AI estimation
  fetch(`${INTERNAL_API_URL}/api/analytics/fatigue-profile/estimate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: exercise.name,
      category: exercise.category,
      equipment: exercise.equipment,
      primary_muscles: exercise.primary_muscles,
      secondary_muscles: exercise.secondary_muscles,
      cues: exercise.cues,
      notes: exercise.notes,
    }),
  })
    .then(res => res.json())
    .then(profile => {
      // Update exercise in DynamoDB with profile
      updateExerciseProfile(exercise.id, {
        fatigue_profile: { axial: profile.axial, neural: profile.neural, peripheral: profile.peripheral, systemic: profile.systemic },
        fatigue_profile_source: 'ai_estimated',
        fatigue_profile_reasoning: profile.reasoning,
      })
    })
    .catch(err => console.error('Fatigue profile estimation failed:', err))
}
```

## Step 4: Create Backfill Script

**New file:** `scripts/backfill_fatigue_profiles.py`

Python script that:
1. Connects to DynamoDB (`if-health` table, `pk="operator"`, `sk="glossary#v1"`)
2. Reads all exercises from the glossary
3. For each exercise where `fatigue_profile` is null or `fatigue_profile_source` is not `"manual"`:
   - Calls the `estimate_fatigue_profile()` function directly (import from `app.src.health.fatigue_ai`)
   - Updates the exercise dict with the returned profile
4. Writes the updated glossary back to DynamoDB
5. Logs each exercise name + result for review

Options:
- `--dry-run`: Print what would be estimated without saving
- `--exercise NAME`: Target a single exercise by name
- Rate-limit LLM calls (add 1-2 second delay between calls)

```python
"""Backfill fatigue profiles for all glossary exercises that don't have one.

Usage:
    python scripts/backfill_fatigue_profiles.py [--dry-run] [--exercise "Barbell Row"]
"""
import argparse
import asyncio
import json
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import boto3
from src.health.fatigue_ai import estimate_fatigue_profile
from src.config import *

TABLE_NAME = "if-health"

def get_glossary(dynamodb):
    """Fetch glossary from DynamoDB."""
    # ...

def save_glossary(dynamodb, exercises):
    """Save updated glossary to DynamoDB."""
    # ...

async def backfill(dry_run=False, exercise_name=None):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(TABLE_NAME)
    exercises = get_glossary(table)

    for ex in exercises:
        if exercise_name and ex['name'] != exercise_name:
            continue
        if ex.get('fatigue_profile') and ex.get('fatigue_profile_source') == 'manual':
            print(f"SKIP (manual): {ex['name']}")
            continue

        print(f"Estimating: {ex['name']}...")
        profile = await estimate_fatigue_profile(ex)

        if dry_run:
            print(f"  -> {json.dumps(profile, indent=2)}")
        else:
            ex['fatigue_profile'] = {k: profile[k] for k in ['axial', 'neural', 'peripheral', 'systemic']}
            ex['fatigue_profile_source'] = 'ai_estimated'
            ex['fatigue_profile_reasoning'] = profile.get('reasoning')
            print(f"  -> Saved profile for {ex['name']}")

        time.sleep(1)  # Rate limit

    if not dry_run:
        save_glossary(table, exercises)
        print(f"Saved {len(exercises)} exercises")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--exercise', type=str, default=None)
    args = parser.parse_args()
    asyncio.run(backfill(dry_run=args.dry_run, exercise_name=args.exercise))
```

## Verification
- `npm run build` in both `frontend/` and `backend/` of powerlifting-app
- Open glossary page, edit an exercise — verify 4 sliders appear
- Change a slider — verify source badge flips to "Manual override"
- Click "Re-estimate" — verify values update and source returns to "AI estimated"
- Create a new exercise — verify AI estimation triggers automatically after save
- Run `python scripts/backfill_fatigue_profiles.py --dry-run` to preview without saving
