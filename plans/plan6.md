## Plan 6 — Subjective Wellness Capture

**Goal:** Add a minimal pre-session wellness prompt that becomes an input for the revised readiness score (Plan 7). Prereq for Plan 7.

**Files:**
- `packages/types/index.ts` (extend `Session` with `wellness` object)
- `backend/src/routes/analytics.ts` (pass-through)
- `frontend/src/pages/SessionPage.tsx` or equivalent session log entry component
- `tools/health/analytics.py` (aggregate average wellness for readiness window)
- `README.md` "Sessions and exercises" section
- About page (new "Subjective wellness" subsection)

**Schema:**

```ts
interface SessionWellness {
  sleep: 1 | 2 | 3 | 4 | 5
  soreness: 1 | 2 | 3 | 4 | 5    // 1 = very sore, 5 = no soreness
  mood: 1 | 2 | 3 | 4 | 5
  stress: 1 | 2 | 3 | 4 | 5      // 1 = very stressed, 5 = calm
  energy: 1 | 2 | 3 | 4 | 5
  recorded_at: string            // ISO timestamp
}
```

**UI:**
- Pre-session screen with 5 sliders or 5-button rows. Default to "skip" — do not block session logging.
- Display last 4 weeks' wellness averages on the Dashboard as a small trend strip.

**Aggregate formula (used by Plan 7):**

$$W_{\text{subj}} = 1 - \frac{\text{mean}(\text{sleep, soreness, mood, stress, energy over last 14d})}{5}$$

Returns 0 when athlete feels great (all 5s), 0.8 when athlete feels awful (all 1s). Returns `null` when no wellness rows in window → readiness falls back to pre-Plan-7 behavior for the wellness component.

---
