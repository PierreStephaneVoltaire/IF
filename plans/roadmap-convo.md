This is a genuinely impressive piece of software — the math layer alone (Theil-Sen, ACWR, multi-dimensional fatigue, diminishing-returns projection) is well beyond what most commercial apps do. Here's a structured breakdown of how to think about productisation.

---

## 🎯 Target Audience Analysis

<details>
<summary><strong>Primary Target: Competing & Competition-Prep Athletes (Best Fit)</strong></summary>

These are your core users because your entire stack is built around a competition date as the axis of everything.

**Who they are:**
- Novice–intermediate lifters (first 1–5 comps) — highest pain point, lowest coaching access
- Self-coached intermediates preparing for their first DOTS 300–400 range total
- Athletes who use spreadsheets or nothing at all today

**Why they convert:**
- Your attempt selection, projection, and readiness score solve a *real anxiety* (am I going to bomb out / leave kilos on the platform?)
- They don't have a coach to tell them when to push and when to back off
- The RPE-drift and ACWR features are things they've read about but can't implement manually

**Willingness to pay:** Moderate. $10–20/month is defensible if onboarding is fast.
</details>

<details>
<summary><strong>Secondary Target: Coaches (High Revenue Potential, Harder to Acquire)</strong></summary>

**Who they are:**
- Online coaches managing 5–30 athletes
- Club coaches at small gyms who don't have software beyond Google Sheets

**Why they're valuable:**
- They pay for multiple seats or a flat platform fee
- They become a distribution channel — one coach brings 10+ athletes
- Your correlation analysis and program evaluation tools read as *professional-grade* to them

**Why they're hard:**
- They already have workflows (Google Sheets, TrainHeroic, TrueCoach)
- They need multi-athlete dashboards, not single-athlete portals
- The "single-athlete scope" limitation in your README is the blocker — you'd need to solve this first

**Don't target coaches until** you have a multi-athlete view.
</details>

<details>
<summary><strong>Tertiary: Gyms / Clubs</strong></summary>

Low priority for now. Gyms want check-ins, billing, and class scheduling — your product doesn't serve that. **Powerlifting-specific clubs** (not globo gyms) are more interesting but tiny market. Revisit after coaches are solved.
</details>

---

## 🏗️ Feature Prioritisation Matrix

Below is every feature you mentioned, rated against **impact vs. build complexity** and tagged by which audience it serves.

| Feature | Audience | Impact | Complexity | Priority |
|---|---|---|---|---|
| **OpenPowerlifting benchmarking** (already roadmapped) | Athletes | 🔥 High | Low | **Do first** |
| **Excel import** (roadmapped) | Athletes | 🔥 High | Medium | **Do first** |
| **Nearby competition listing** | Athletes | High | Medium | Soon |
| **Competition cost estimator** | Athletes | Medium | Low | Soon |
| **Supplement prioritisation by goal/budget** | Athletes | Medium | High (needs Examine) | After Examine.com |
| **Budget tracker (gym sub, supps, comp fees)** | Athletes | Medium | Low | Soon |
| **Coach–athlete collaboration** | Coaches + Athletes | 🔥 High | High | Multi-athlete milestone |
| **Program builder** | Athletes + Coaches | 🔥 High | High | After current block is stable |
| **Coach/athlete matching** | Both | Low | High | Avoid (social risk) |
| **Rule explanations per federation** | Athletes | Medium | Low | Quick win |
| **Supplement refill planning** | Athletes | Low | Low | Easy filler |
| **Competition result prediction from past attendances** | Athletes | Medium | High | Later |

---

## 🔥 The Three Features That Will Actually Drive Signups

<details>
<summary><strong>1. OpenPowerlifting Benchmarking (your own roadmap item — do it now)</strong></summary>

This is your biggest conversion driver because it answers the question every competing athlete has:

> *"Am I competitive for my weight class, age, and federation?"*

Your DOTS score is already computed. Plugging into the OpenPowerlifting public dataset gives you:
- Percentile rank in federation × weight class × sex × age bracket
- "You're projecting a 387 DOTS — that puts you in the top 23% of 93kg Open men in the IPF"
- Target total to podium at a specific meet (if you have historical attendance data)

**Why it converts:** It makes your projection feature emotionally meaningful. A projected 280kg total is abstract. "Top 40% in your class" is motivating.
</details>

<details>
<summary><strong>2. Competition Finder + Cost Estimator (new feature)</strong></summary>

Lifters currently hunt for comps on federation websites that are often outdated or painful to navigate. A clean aggregated view with:

- Upcoming meets filtered by federation, country/region, weight class
- Distance from home (or travel cost estimate)
- Predicted comp atmosphere / field size based on historical attendance (OpenPowerlifting has this)
- Auto-populated cost breakdown: entry fee + estimated travel + hotel + cut costs

This is a **low-complexity, high-stickiness** feature. It keeps athletes on your platform during off-season blocks, not just during prep.

**Data source:** OpenPowerlifting, federation RSS/calendar scraping, or a simple user-submission model initially.
</details>

<details>
<summary><strong>3. Program Builder with Phase Templates (your roadmap item)</strong></summary>

Right now your app analyzes a program that already exists. The program builder closes the loop — athletes design the block *inside* your system, so all the analytics fire from day one with no import friction.

Key requirement: it must output to your existing data model (phases → sessions → sets) without requiring hand-entry of every set. Template-based (e.g., "9-week comp prep, 3 days/week, SBD focus") is enough for V1.

**Why it matters for marketability:** Without it, the onboarding story is "log your existing training, then get insights." With it, the story becomes "build your program here and we'll guide you all the way to the platform."
</details>

---

## 💰 Budget & Financial Tracking

This is a sleeper feature with very low build cost. Powerlifting is expensive and nobody tracks it systematically.

A simple budget module covering:

```
Monthly: gym subscription, coaching fee, supplement restocking (with refill prediction based on doses you already store)
Per-comp: entry fee, travel, hotel, kit/equipment, weight cut costs
Annual rollup
```

Your supplement stack is already stored with doses — you can calculate a **burn rate and restock date** from that data with almost no additional input. This is a *"wow, I didn't expect that"* moment for users.

---

## 🤝 Coach–Athlete Collaboration (Do It Right, Not Fast)

You're right to be wary of becoming a social platform. The risk is real. The way to avoid it:

**What to build:**
- A coach gets a read-only (or comment-only) view of an athlete's dashboard
- Coach can flag sessions, leave text annotations on the program evaluation
- Athlete shares via invite link with expiry — no public profiles, no discovery feed

**What NOT to build:**
- Athlete/coach marketplace or matching (you said this — agree completely)
- Public profiles
- Feed, likes, or any social graph

The collaboration feature should feel like *shared Google Doc access*, not Instagram.

---

## 🏛️ Federation Rule Explanations

Quick win, zero AI cost. A structured rule reference per federation (IPF, USAPL, CPU, etc.):

- Equipment specs (belt width, squat depth, knee wraps vs sleeves)
- Weigh-in rules and timing
- Attempt change windows
- Red light reasons and how to avoid them

This is static content that makes your app the "one tab" a lifter needs during meet prep. Pair it with your attempt selection feature and it's genuinely useful.

---

## 🗺️ Suggested Product Roadmap

```
Phase 1 — Make the core sticky (now)
├── OpenPowerlifting benchmarking
├── Excel import (log + program)
├── Competition finder (scrape / manual submission)
└── Budget tracker + supplement refill prediction

Phase 2 — Widen the funnel
├── Program builder with templates
├── Federation rule reference
└── Examine.com supplement + nutrition layer

Phase 3 — Coach tier (new revenue)
├── Multi-athlete dashboard
├── Coach read/annotate access
└── Coach pricing tier ($X per athlete seat)

Phase 4 — Predictive & social-adjacent
├── Meet field size / competitiveness prediction
└── Age/sex normalization curves
```

---

## 🎁 Your Existing Differentiators (Don't Undersell These)

Most commercial powerlifting apps (Stronger by Science's app, Juggernaut AI, My Lift) are program *delivery* tools. They don't do what you do:

| What you have | What competitors have |
|---|---|
| Multi-dimensional fatigue model (axial/neural/peripheral/systemic) | Volume × intensity load only |
| Theil-Sen progression (outlier-resistant) | Simple moving average or nothing |
| Diminishing-returns comp projection with DOTS-tiered lambda | Linear extrapolation or coach judgment |
| ACWR per fatigue dimension | Aggregate tonnage ratio only |
| 90th-percentile e1RM (conservative, not optimistic) | Best set or Epley formula |
| RPE drift detection via OLS residuals | None |

These are real, defensible advantages. Lead with **"built on the same statistical methods sports scientists use"** rather than feature lists.

---

**Bottom line:** Your first target is the **self-coached competing athlete** who is past their first comp and serious enough to care about their numbers. OpenPowerlifting benchmarking + competition finder + budget tracker gets you to a launchable product for that person. The coach tier is $$$, but it requires multi-athlete architecture first — treat it as Phase 3.