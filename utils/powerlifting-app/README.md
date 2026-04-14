# Powerlifting Peaking Portal

A single-athlete portal for preparing powerlifting competitions. Quantifies readiness,
peaking trajectory, and attempt selection from the data produced by actual training.

## Why it exists

Peaking is hard to judge by feel — a block that feels smooth can still under-prepare,
and a block that feels brutal can still land a PR total. This portal closes that loop:
every planned session, logged session, RPE entry, bodyweight, and attempt is fed into
deterministic formulas and narrow AI reasoning tools so the decision to push, hold, or
back off is grounded in numbers that came from the athlete&apos;s own training history.

## Data captured (and why we don&apos;t capture more)

Per-meal macros, per-night sleep scores, continuous heart rate, and minute-level HRV
are intentionally out of scope. The signal-to-friction ratio of that kind of daily
micro-logging is poor for a working athlete. Instead:

- **Sessions** — sets, reps, kilograms, RPE, failed-set flags, session bodyweight,
  session RPE, session notes.
- **Competitions** — federation, weight class, date, planned attempts, results.
- **Lift profiles** — per-lift style, sticking points, primary muscle, volume tolerance.
- **Body metrics** — height, bodyweight, arm wingspan, leg length.
- **Diet notes** — average daily calories, macros, sleep hours, water, consistency flag,
  recorded per note window (not per meal or per night).
- **Supplements** — stack and doses (stored; not yet fed to AI — waiting on the planned
  Examine.com integration to map items to evidence before reaching the models).

## Mathematical methodology

Every surfaced metric comes from a documented formula. Full definitions and thresholds
live in [`frontend/src/constants/formulaDescriptions.ts`](frontend/src/constants/formulaDescriptions.ts)
and render on the About page. Five families:

- **Scoring** — DOTS (sex-specific polynomial), estimated 1RM (RTS-based RPE table or
  conservative rep-percentage fallback; 90th percentile over qualifying sessions).
- **Progression** — Theil-Sen slope of e1RM over effective training weeks (deloads and
  break weeks excluded); diminishing-returns projection to competition date.
- **Stress** — INOL, ACWR (acute:chronic workload ratio), fatigue index (failed-set
  ratio × 0.40 + fatigue spike × 0.35 + RPE stress × 0.25), RPE drift.
- **Quality** — specificity ratio, relative-intensity distribution, compliance.
- **Peaking** — attempt selection (projected comp max × attempt percentages, rounded to
  2.5 kg), readiness score (weighted composite of fatigue, RPE drift, bodyweight
  stability, miss rate, compliance).

## AI reasoning layer

Three narrow tools. Each receives only the subset of data it needs.

- **Fatigue profile estimation** — per-exercise axial / neural / peripheral / systemic
  estimates. Receives exercise metadata plus optional athlete body metrics and lift
  profile for leverage-aware adjustments.
- **Correlation analysis** — weekly e1RM trends, accessory volumes, lift profiles,
  athlete measurements, and per-accessory ROI (pearson r between weekly volume and
  average intensity). Reports anatomically-plausible accessory-to-lift correlations only.
- **Program evaluation** — full current block with phases, competitions, completed and
  planned sessions, lift profiles, measurements, diet context, supplements (for now),
  weekly analytics report, and exercise ROI. Produces a conservative stance
  (continue / monitor / adjust / critical) with specific data-cited reasoning.

## Known limitations

- **Chronobiology** — training-time vs meet-flight timing is not modeled.
- **Supplementation** — stored, not analyzed. Examine.com integration pending.
- **Diet and sleep granularity** — averages only, by design. Examine.com-backed nutrition
  reasoning pending.
- **Biometric precision** — limb lengths are AI context only; they don&apos;t enter the
  rigid fatigue formulas.
- **No video analysis** — bar path, rep consistency, and technique regressions are not
  captured. Velocity loss is inferred from RPE and failed sets.
- **Single-athlete scope** — calibrations and defaults are tuned for one athlete.
  Population normalization is roadmap, not current.

## Roadmap

- **Excel workout import** — upload a filled training log and run the same analysis on it.
- **Excel program import** — upload a program spec (phases, templates, exercises) to seed
  a new block without hand-entry.
- **Examine.com supplement reasoning** — map each supplement to its evidence base before
  exposing it to the AI tools, so the models reason about substantiated effects rather
  than raw names.
- **Examine.com nutrition reasoning** — same approach for calories, macros, sleep, and
  water.
- **OpenPowerlifting benchmarking** — score readiness and projected totals against
  federation, weight class, age, and sex cohorts.
- **Age and sex normalization** — adjust e1RM and DOTS trajectories against age-graded
  curves and sex-specific recovery profiles.
- **In-session adjustments** — mid-session load or set corrections triggered by acute
  fatigue, failed sets, or injury flags.

## Tech stack

- **Frontend** — React 19 + Vite, TypeScript, Mantine, Lucide, Zustand, Recharts.
- **Backend** — Node.js Express (DynamoDB CRUD + S3 video), Python tools (statistical
  engine + AI reasoning).
- **Storage** — DynamoDB single-table (`if-health`).

## Running locally

```bash
# Frontend (port 5173)
cd frontend && npm install && npm run dev

# Backend (port 3001)
cd backend && npm install && npm run dev
```

The frontend dev server proxies `/api/*` calls to the Express backend.
