
## Plan 17 — Plain-English Alerts Layer

**Goal:** Above the raw metrics on the Analysis page, render a small ordered list of coaching-language alerts generated deterministically from the analytics response. No AI. Nerd view still available via formula accordion.

**Files:**
- `frontend/src/components/analysis/AlertsStrip.tsx` (new)
- `frontend/src/pages/AnalysisPage.tsx` (mount at top)
- `tools/health/analytics.py` (extend with `generate_alerts` that emits structured alerts)

**Alert structure:**
```ts
interface AnalyticsAlert {
  severity: 'info' | 'caution' | 'warning'
  source: 'acwr' | 'fatigue' | 'readiness' | 'projection' | 'specificity' | 'banister' | 'decoupling' | 'monotony'
  message: string          // plain-English coaching line
  raw_detail: string       // short technical line for expand-on-click
}
```

**Deterministic mapping table (extend with every formula plan):**

| Condition | Severity | Message |
|---|---|---|
| `fatigue_index >= 0.60` and trending up | warning | "Fatigue is elevated. Consider a lighter session or deload this week." |
| `acwr_composite > 1.50` and phase intent ≠ overreach | warning | "Training load jumped sharply. Monitor recovery closely." |
| `acwr_composite > 1.50` during planned overreach | info | "Load spike is consistent with your planned overreach." |
| `decoupling_fatigue_dominant` for 3+ weeks | warning | "Strength is flat but fatigue is climbing. Accumulated stress is outpacing adaptation." |
| `tsb_today < -30` | warning | "You are in deep overload. Performance should rebound after a deload." |
| `tsb_today` in [+5, +15] and `weeks_to_comp <= 2` | info | "You're in the peaking window for your upcoming meet." |
| `specificity_below_expected` | caution | "More competition-lift practice recommended given how close your meet is." |
| `high_monotony` | caution | "Your daily training load is very uniform. Consider more contrast between hard and easy days." |
| `projected_total >= qualifying_total` (Plan 25) | info | "You're projected to exceed the qualifying total for this meet." |
| `projected_total < qualifying_total` with < 6 weeks out | caution | "Your projected total is below the meet's qualifying standard." |
| `readiness < 50` for 2+ weeks | warning | "Readiness has been low consistently. Check sleep and stress." |

Each alert is clickable → expands to show the raw metric value and links to the formula accordion entry.

---
