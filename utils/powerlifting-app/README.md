# Powerlifting Peaking Portal

A high-signal statistical analysis engine and peaking laboratory for competitive powerlifters. This is not a coaching app; it is a data-driven tool designed to quantify program effectiveness, manage fatigue dimensions, and maximize platform performance.

## Core Philosophy

- **Statistical over Subjective:** We prioritize objective metrics (ACWR, INOL, Theil-Sen regressions) over "feel," while using RPE as a proxy for velocity and neurological state.
- **Friction vs. Signal:** We avoid tedious daily tracking (macros, heart rate, sleep cycles). Instead, we focus on high-impact data: loads, RPE, bodyweight, and estimated fatigue.
- **Peaking Focus:** The entire architecture is built around the "Peaking Block"

## Tech Stack

- **Frontend:** React 19 + Vite, TypeScript, Mantine (UI), Lucide (icons), Zustand (state), Recharts (visualization).
- **Backend:** Node.js Express (DynamoDB CRUD + S3 Video), Python FastAPI (Advanced Analytics Engine).
- **Database:** DynamoDB single-table (`if-health`).
- **AI Integration:** LLM-based reasoning for exercise fatigue profiling and qualitative program evaluation.

## Mathematical Methodology

The portal employs several key formulas to derive its insights:

### 1. Strength & Intensity

- **Estimated 1RM (e1RM):** Uses a hybrid approach. For sets with RPE, we use a standard RTS-based RPE lookup table. For sets without RPE, we fall back to a conservative 5-rep table or the **Epley Formula**: `e1RM = weight * (1 + reps / 30)`.
- **DOTS Score:** A sex-specific polynomial formula measuring relative strength:
  `DOTS = 500 * total / (a + b*bw + c*bw² + d*bw³ + e*bw⁴)`
- **INOL (Intensity Number of Lifts):** Measures set-level stress relative to intensity:
  `INOL = reps / (100 * (1 - Intensity))`

### 2. Fatigue & Readiness

- **ACWR (Acute:Chronic Workload Ratio):** Compares the current week's fatigue load to the 4-week chronic average.
  `ACWR = Fatigue_Week / Avg(Fatigue_Prev_4_Weeks)`
- **Fatigue Dimensions:** AI-estimated coefficients for 4 dimensions:
  - **Axial:** Spinal compression and loading.
  - **Neural:** CNS demand (scaled quadratically above 60% intensity).
  - **Peripheral:** Localized muscle damage.
  - **Systemic:** Total metabolic/cardiovascular demand.
- **Readiness Score:** A 0-100 composite of fatigue, RPE drift (actual vs. target RPE), bodyweight stability, and session compliance.

### 3. Projections

- **Diminishing Returns Projection:** Projects meet totals using a decay model based on your current DOTS level:
  `C_max = [E_now + Δw * λ * (1 - λⁿ) / (1 - λ)] * P`
  (Where `λ` is the decay factor and `P` is the peaking bonus).

## Imperfections & Context

- **Chronobiology:** The model does not yet account for "Flight Timing" (training in the evening vs. competing in the morning).
- **Supplements:** Ergogenic aids (creatine, caffeine) are not currently factored into the fatigue dimensions.
- **Biometrics:** Bone lengths and lift styles (e.g., sumo vs. conventional) are captured but primarily used for AI-based fatigue estimation rather than rigid physics modeling.

## Roadmap

- **OpenPowerlifting Integration:** Benchmarking your readiness against global populations, filtered by age, sex, federation, and time period.
- **In-Session Ad Hoc:** Real-time logic to adjust planned weights/sets mid-session based on injury, acute fatigue, or failed sets.
- **Demographic Normalization:** Adjusting e1RM trajectories based on age-graded performance curves.

## Running Locally

```bash
# Frontend (port 5173)
cd frontend && npm install && npm run dev

# Backend (port 3001)
cd backend && npm install && npm run dev
```

The frontend dev server proxies `/api/*` calls to the Express backend.
