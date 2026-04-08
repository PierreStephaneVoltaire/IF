

## 2. Health: Export + Statistical Analysis

### Excel Export

Straightforward. `openpyxl` in a tool plugin, specialist calls `export_program_history(program_id, format="xlsx")`, file lands in the sandbox, `FILES:` metadata delivers it. The portal gets an export button that hits the same tool via API. Nothing fancy.

### Statistical Analysis Skill — This Is the Interesting One

You're exactly right that the AI shouldn't do the math. The pattern you're describing is:

```
Agent (reasoning, selection, interpretation)
  → Deterministic skill (algorithms, math, statistics)
    → Structured output (numbers, charts, correlations)
      → Agent (summarizes findings in human terms)
```

Pre-built algorithms the agent orchestrates rather than implements:

| Algorithm | Input | Output |
|-----------|-------|--------|
| **Progression rate** | Session history for a lift | Weekly/monthly rate of change (kg/week), linear vs actual curve |
| **Volume-intensity correlation** | Sessions over N weeks | Whether volume and intensity are tracking inversely (as they should in periodization) |
| **RPE drift detection** | RPE logs vs actual load | Whether RPE is trending up at same loads (fatigue) or down (adaptation) |
| **Fatigue index** | Volume, RPE, bodyweight, sleep signals from diary | Composite fatigue score — flag overreaching |
| **1RM estimation** | Recent sets × reps × RPE | Estimated 1RM via Epley/Brzycki/RPE-based tables |
| **Wilks/DOTS tracking** | Totals + bodyweight over time | Competition-normalized strength over time |
| **Periodization compliance** | Planned vs actual volume/intensity per block | Are you following the program or drifting |
| **Meet projection** | Current estimated 1RMs + historical peaking response | Projected total at meet date |

These are all deterministic — no LLM involved. The agent's job is:
1. Decide which analyses are relevant right now (6 weeks out from comp? run meet projection and fatigue index)
2. Call the skill with the right parameters
3. Interpret the output ("your squat RPE is drifting up at the same loads — early sign of accumulated fatigue, consider a deload")

### Weekly Analysis Tool

This is better than raw DynamoDB dumps for exactly the reason you said. Build it as a scheduled tool (or a `/weekly` command):

```
Weekly analysis tool runs:
  → Pull last 7 days of sessions from DynamoDB
  → Run progression rate, RPE drift, fatigue index, periodization compliance
  → Output structured JSON:
    {
      "week": 12,
      "block": "peaking",
      "lifts": {
        "squat": {"volume_change": -15%, "intensity_change": +8%, "rpe_trend": "stable"},
        ...
      },
      "fatigue_index": 0.72,
      "compliance": 0.95,
      "flags": ["bench_rpe_drift_up"],
      "projection": {"total": 573, "confidence": 0.8}
    }
  → Portal renders it directly (chart, traffic lights, projections)
  → Agent gets a summary it can reference in conversation
```

The portal displays the structured output. The agent references it conversationally. Neither is doing the other's job.

**docs**: "AI agent orchestrates deterministic statistical algorithms rather than attempting math" is a mature design choice that demonstrates you understand LLM limitations. That's exactly the kind of judgment AI companies look for.