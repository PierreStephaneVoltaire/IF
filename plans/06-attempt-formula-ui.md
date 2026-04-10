# Plan 6: Attempt Selector + Formula Info UI (Sections 13, 14)

## Context
Plans 1-5 fixed all formulas and added all new metrics. This plan adds the attempt selector (preference-based competition attempt calculator) and the formula info UI section (collapsible reference explaining how every metric is calculated).

## Files to Modify
- `app/src/health/analytics.py` — add `compute_attempt_selection()`
- `utils/powerlifting-app/packages/types/index.ts` — add attempt_pct to ProgramMeta
- `utils/powerlifting-app/frontend/src/api/analytics.ts` — add attempt_selection to WeeklyAnalysis
- `utils/powerlifting-app/frontend/src/pages/AnalysisPage.tsx` — add attempt selector settings + formula info section
- `utils/powerlifting-app/frontend/src/constants/formulaDescriptions.ts` (NEW) — formula description constants

## Step 1: Add Attempt Selection Logic (Section 13)

### 1a. Update ProgramMeta TypeScript type

**File:** `utils/powerlifting-app/packages/types/index.ts`

Add to `ProgramMeta` interface:
```typescript
attempt_pct?: {
  opener: number   // default 0.90
  second: number   // default 0.955
  third: number    // default 1.00
}
```

### 1b. Add `compute_attempt_selection()` to analytics.py

**File:** `app/src/health/analytics.py`

New function:
```python
def compute_attempt_selection(
    projected_maxes: dict,
    attempt_pct: dict | None = None,
) -> dict | None:
    """Compute competition attempts from projected maxes and user preferences."""
```

Logic:
1. If no `attempt_pct` provided, use defaults: `{"opener": 0.90, "second": 0.955, "third": 1.00}`
2. For each lift with a projected max (`C_max`):
   - `opener = round_to_nearest_2_5(C_max * pct.opener)`
   - `second = round_to_nearest_2_5(C_max * pct.second)`
   - `third = round_to_nearest_2_5(C_max * pct.third)`
3. Helper: `round_to_nearest_2_5(val) = round(val / 2.5) * 2.5`
4. Return:
```python
{
    "squat": {"opener": 180.0, "second": 192.5, "third": 200.0},
    "bench": {"opener": 112.5, "second": 120.0, "third": 125.0},
    "deadlift": {"opener": 210.0, "second": 222.5, "third": 232.5},
    "total": 557.5,  # sum of thirds
    "attempt_pct_used": {...},  # the actual percentages used
}
```

Return `None` if no competitions exist or no projected maxes available.

### 1c. Integrate into `meet_projection()`

In the `meet_projection()` function (or as a separate call in `weekly_analysis()`), after computing projected maxes for each lift, also compute attempts.

In `weekly_analysis()`:
```python
# After meet projection computation
attempt_pct = program.get("meta", {}).get("attempt_pct")
if projections:
    "attempt_selection": compute_attempt_selection(projected_maxes, attempt_pct)
```

### 1d. Add attempt_selection to WeeklyAnalysis type

**File:** `utils/powerlifting-app/frontend/src/api/analytics.ts`

```typescript
attempt_selection?: Record<string, {
  opener: number
  second: number
  third: number
}> & { total?: number }
```

## Step 2: Formula Info UI Section (Section 14)

### 2a. Create formula descriptions constants

**New file:** `utils/powerlifting-app/frontend/src/constants/formulaDescriptions.ts`

Export 14 formula description objects. Each has:
```typescript
export interface FormulaDescription {
  id: string
  title: string
  summary: string                    // One-line plain English
  formula: string                    // Pre-formatted code block
  variables: { name: string; description: string }[]
  thresholds?: { label: string; value: string; flag?: string }[]
}
```

The 14 formulas (from spec section 14):

1. **Estimated 1RM** — RPE table (reps≤6) or conservative table (reps≤5). 90th percentile of qualifying sets over 6 weeks. No Epley/Brzycki.
2. **Progression Rate** — Theil-Sen regression on e1RM per effective training week. Deloads/breaks excluded.
3. **Competition Projection** — `C_max = [E_now + delta_w * lambda * (1 - lambda^n) / (1 - lambda)] * P`, clamped to [E_now, E_now * 1.10]
4. **Attempt Selection** — `attempt_k = round_to_2.5(C_max * pct_k)` with user-configurable percentages
5. **Fatigue Model** — 4 dimensions (axial, neural, peripheral, systemic) per exercise. AI-estimated or manual. Per-set: `F_d = profile.d * weight * reps` (neural uses `phi(I)` scaling)
6. **Fatigue Index** — `0.40 * failed_compound_ratio + 0.35 * composite_spike + 0.25 * skip_rate`
7. **INOL** — `sum(reps / (100 * (1 - I)))` per lift per week. Flags: <2.0 low, 2.0-4.0 productive, >4.0 overreaching
8. **ACWR** — Per-dimension: `F_d_week / mean(F_d previous 4 non-deload weeks)`. Composite: weighted average (axial 0.30, neural 0.30, peripheral 0.25, systemic 0.15). Zones: <0.8 undertraining, 0.8-1.3 optimal, 1.3-1.5 caution, >1.5 danger
9. **Relative Intensity Distribution** — `RI = weight / E_now`. Buckets: heavy >0.85, moderate 0.70-0.85, light <0.70
10. **Specificity Ratio** — `SR_narrow = SBD sets / total sets`, `SR_broad = (SBD + secondary category) / total sets`
11. **Readiness Score** — `R = (1 - (0.30*F_norm + 0.25*D_rpe + 0.20*S_bw + 0.15*M_rate + 0.10*(1-C_pct/100))) * 100`. Green >75, yellow 50-75, red <50
12. **DOTS Score** — `500 * total / (a + b*bw + c*bw^2 + d*bw^3 + e*bw^4)` with sex-specific coefficients
13. **RPE Drift** — Residual regression: `residual = avg_rpe - phase_target_midpoint`. Slope >= 0.1 → fatigue, <= -0.1 → adaptation
14. **Compliance** — `(completed / planned) * 100`. Deload/break weeks excluded from both numerator and denominator

### 2b. Add Formula Reference section to AnalysisPage

**File:** `utils/powerlifting-app/frontend/src/pages/AnalysisPage.tsx`

At the bottom of the page, before the flags section, add a collapsible "How These Numbers Are Calculated" section:

```tsx
{/* Formula Reference */}
<div className="mt-8">
  <details className="group">
    <summary className="cursor-pointer text-sm font-medium text-gray-400 hover:text-gray-200">
      How These Numbers Are Calculated
    </summary>
    <div className="mt-4 space-y-2">
      {FORMULA_DESCRIPTIONS.map(formula => (
        <details key={formula.id} className="border border-gray-700 rounded-lg">
          <summary className="px-4 py-2 cursor-pointer text-sm font-medium">
            {formula.title}
          </summary>
          <div className="px-4 py-3 space-y-2 text-sm text-gray-300">
            <p>{formula.summary}</p>
            <pre className="bg-gray-800 rounded p-3 font-mono text-xs overflow-x-auto">
              {formula.formula}
            </pre>
            {formula.variables && (
              <div className="grid grid-cols-2 gap-1 text-xs">
                {formula.variables.map(v => (
                  <div key={v.name}><code>{v.name}</code>: {v.description}</div>
                ))}
              </div>
            )}
            {formula.thresholds && (
              <table className="w-full text-xs mt-2">
                <thead><tr><th>Condition</th><th>Value</th><th>Flag</th></tr></thead>
                <tbody>
                  {formula.thresholds.map(t => (
                    <tr key={t.label}><td>{t.label}</td><td>{t.value}</td><td>{t.flag || '—'}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      ))}
    </div>
  </details>
</div>
```

Use native HTML `<details>/<summary>` elements (no additional dependencies needed). This gives collapsible behavior for free.

### 2c. Add Attempt Selector Settings Panel

In the AnalysisPage, add a collapsible settings panel for attempt percentages:

```tsx
{/* Attempt Selector Settings */}
{analysis?.attempt_selection && (
  <div className="mt-6 border border-gray-700 rounded-lg p-4">
    <h3 className="text-sm font-medium mb-3">Competition Attempt Percentages</h3>
    <div className="grid grid-cols-3 gap-4">
      <div>
        <label className="text-xs text-gray-400">Opener</label>
        <input type="number" step="0.005" min="0.80" max="0.95" defaultValue={0.90}
          className="..." />
        <p className="text-xs text-gray-500 mt-1">Should feel easy under worst conditions</p>
      </div>
      <div>
        <label className="text-xs text-gray-400">Second</label>
        <input type="number" step="0.005" min="0.90" max="0.98" defaultValue={0.955}
          className="..." />
        <p className="text-xs text-gray-500 mt-1">A confident single, builds momentum</p>
      </div>
      <div>
        <label className="text-xs text-gray-400">Third</label>
        <input type="number" step="0.005" min="0.95" max="1.05" defaultValue={1.00}
          className="..." />
        <p className="text-xs text-gray-500 mt-1">Your projected max — go for it</p>
      </div>
    </div>
    {/* Display computed attempts */}
    <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
      {Object.entries(analysis.attempt_selection).filter(([k]) => k !== 'total' && k !== 'attempt_pct_used').map(([lift, attempts]) => (
        <div key={lift} className="text-center">
          <div className="font-medium capitalize">{lift}</div>
          <div className="text-xs text-gray-400">
            {attempts.opener} / {attempts.second} / {attempts.third}
          </div>
        </div>
      ))}
    </div>
  </div>
)}
```

Wire the inputs to save `attempt_pct` to program meta via the existing program update API.

## Step 3: Final Verification

- Run `npm run build` in both `frontend/` and `backend/` of powerlifting-app
- Run the Python app
- Hit `GET /v1/health/analysis/weekly?weeks=4` and verify `attempt_selection` present when competition exists
- Open the analysis page and verify:
  - Formula reference section is collapsed at bottom
  - Expanding shows all 14 formula panels
  - Attempt selector shows when competition is upcoming
  - All new metric cards from Plan 5 render correctly
- Full backward compat: verify page doesn't error if backend returns old format (missing new optional fields)
