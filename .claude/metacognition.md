# Metacognitive System

Self-reflective capabilities for learning from experience, tracking limitations, and improving over time.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    REFLECTION ENGINE CYCLE                        │
│                                                                  │
│  1. POST-SESSION REFLECTION                                      │
│     - Summarize what happened                                    │
│     - Identify what worked / what failed                         │
│     - Log capability gaps hit                                    │
│     - Detect misconceptions surfaced                             │
│     - Store as session_reflection                                │
│                             │                                    │
│                             ▼                                    │
│  2. PATTERN DETECTION                                            │
│     - Cluster recent topics by semantic similarity               │
│     - Detect temporal patterns                                   │
│     - Detect skill gap patterns                                  │
│     - Update frequency + confidence or create new                │
│                             │                                    │
│                             ▼                                    │
│  3. OPINION FORMATION                                            │
│     - Review user opinions without agent responses               │
│     - Form agent position with reasoning                         │
│     - Store as opinion_pair                                      │
│                             │                                    │
│                             ▼                                    │
│  4. CAPABILITY GAP ANALYSIS                                      │
│     - Aggregate gaps by frequency                                │
│     - Generate acceptance criteria for top gaps                  │
│     - Promote high-priority gaps to tool_suggestion              │
│                             │                                    │
│                             ▼                                    │
│  5. META-ANALYSIS                                                │
│     - Category distribution (what's growing?)                    │
│     - Stale fact detection                                       │
│     - Category fit analysis                                      │
│                             │                                    │
│                             ▼                                    │
│  6. OPERATOR GROWTH TRACKING                                     │
│     - Review misconceptions: any repeated?                       │
│     - Review skill assessments: improvement trend?               │
│     - Generate learning suggestions                              │
└──────────────────────────────────────────────────────────────────┘
```

## When It Runs

| Trigger | Condition | Description |
|---------|-----------|-------------|
| Post-session | >5 exchanges | After substantive conversations |
| Periodic | Every 6 hours | Background analysis |
| On-demand | `/reflect` command | Manual trigger |
| Threshold | Store size limits | When thresholds are hit |

## Components

### Reflection Engine

**Module:** `src/agent/reflection/engine.py`

Orchestrates the full reflection cycle.

### Pattern Detector

**Module:** `src/agent/reflection/pattern_detector.py`

Detects recurring themes in operator behavior.

**Pattern Types:**
- `temporal`: Time-based patterns ("Asks about AWS every Monday")
- `topical`: Subject clustering ("Networking questions cluster together")
- `behavioral`: Action patterns ("Prefers step-by-step explanations")
- `skill_gap`: Learning patterns ("Repeated basic questions in domain")

### Opinion Formation

**Module:** `src/agent/reflection/opinion_formation.py`

Creates agent positions on user-stated opinions.

**Agreement Levels:**
- `agree`: Agent agrees with user position
- `partial`: Agent partially agrees
- `disagree`: Agent disagrees with reasoning
- `insufficient_data`: Not enough information

### Meta Analyzer

**Module:** `src/agent/reflection/meta_analysis.py`

Examines the fact store for patterns and health metrics.

### Growth Tracker

**Module:** `src/agent/reflection/growth_tracker.py`

Monitors operator learning and identifies knowledge gaps.

## Capability Gap Tracking

**Module:** `src/agent/tools/capability_tracker.py`

### Gap Lifecycle

```
User asks for something → Agent can't do it
         ↓
Log capability_gap {content, context, timestamp}
         ↓
Reflection engine aggregates → trigger_count++
         ↓
threshold (trigger_count >= 3)?
    No → Continue tracking
    Yes → Generate acceptance criteria
          Compute priority score
          Promote to tool_suggestion
          Surface via /gaps command
```

### Priority Score Formula

```
priority = (trigger_count / max_triggers) * 0.4
         + recency_weight * 0.3
         + impact_estimate * 0.3

Where recency_weight = e^(-0.05 * days_since_last_seen)
```

## Commands

| Command | Action | Example Output |
|---------|--------|----------------|
| `/reflect` | Trigger manual reflection cycle | "Reflection cycle initiated" |
| `/gaps` | List capability gaps by priority | Priority, Status, Triggers, Description |
| `/patterns` | Show detected patterns | Pattern types with frequency and confidence |
| `/opinions` | Show opinion pairs | User vs agent positions with reasoning |
| `/growth` | Show operator growth report | Knowledge gaps, skill trends, abandoned interests |
| `/meta` | Show store health metrics | Category distribution, suggestions |
| `/tools` | Show tool suggestions from gaps | Priority, acceptance criteria, example triggers |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REFLECTION_ENABLED` | `true` | Enable/disable reflection engine |
| `REFLECTION_PERIODIC_HOURS` | `6.0` | Hours between periodic reflections |
| `REFLECTION_POST_SESSION_MIN_TURNS` | `5` | Minimum turns before post-session reflection |
| `REFLECTION_THRESHOLD_UNCATEGORIZED` | `20` | Uncategorized facts to trigger reflection |
| `REFLECTION_THRESHOLD_GAPS_NO_CRITERIA` | `5` | Gaps without criteria to trigger |
| `REFLECTION_THRESHOLD_OPINIONS_NO_RESPONSE` | `10` | Opinions needing response to trigger |
| `CAPABILITY_GAP_PROMOTION_THRESHOLD` | `3` | Triggers needed to promote gap to tool suggestion |

## How to Extend

### Add a new pattern type

1. Edit `src/agent/reflection/pattern_detector.py`
2. Add detection logic in `detect_patterns()`
3. Add to `PatternType` enum if needed

### Add a new reflection trigger

1. Edit `src/agent/reflection/engine.py`
2. Add threshold check in `should_run_reflection()`
3. Add corresponding config variable in `src/config.py`
