# Orchestrator System

Multi-step task execution and parallel analysis through subagent delegation.

**Modules:**
- `src/orchestrator/__init__.py` — Module exports
- `src/orchestrator/executor.py` — Plan execution engine
- `src/orchestrator/analyzer.py` — Parallel analysis

## Key Features

1. **Plan Execution**: Sequential multi-step task execution with subagents
2. **Parallel Analysis**: Code analysis from multiple perspectives simultaneously
3. **Subagent Delegation**: Main agent can delegate complex work to specialized subagents

## Tools

### execute_plan

Execute a multi-step plan with sequential subagent calls.

```python
execute_plan(
    goal: str,           # Overall objective
    steps: List[dict]    # List of {"description", "tool", "expected_output"}
) -> str
```

### analyze_parallel

Analyze code from multiple perspectives in parallel.

```python
analyze_parallel(
    code: str,                    # Code to analyze
    perspectives: List[str] = None  # Optional: custom perspectives
) -> str
```

## Pre-defined Analysis Perspectives

- **Security**: Vulnerability assessment, attack surface analysis
- **Performance**: Bottlenecks, optimization opportunities
- **Architecture**: Design patterns, modularity, extensibility
- **Code Quality**: Readability, maintainability, best practices
- **Testing**: Coverage gaps, test quality

## Data Models

```python
@dataclass
class PlanStep:
    description: str          # What this step accomplishes
    tool: str                 # Tool or approach to use
    expected_output: str      # Expected result

@dataclass
class ExecutionPlan:
    goal: str                 # Overall objective
    steps: List[PlanStep]     # Sequential steps

@dataclass
class StepResult:
    step: PlanStep
    success: bool
    output: str
    error: Optional[str]
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ORCHESTRATOR_SUBAGENT_MODEL` | `@preset/standard` | Model for plan execution subagents |
| `ORCHESTRATOR_ANALYSIS_MODEL` | `@preset/air` | Model for parallel analysis |
| `ORCHESTRATOR_SYNTHESIS_MODEL` | `@preset/standard` | Model for synthesizing analysis results |
| `ORCHESTRATOR_MAX_TURNS` | `15` | Maximum turns per subagent |
| `ORCHESTRATOR_ANALYSIS_MAX_TURNS` | `10` | Maximum turns for analysis subagents |

## How to Extend

### Add a new analysis perspective

1. Edit `src/orchestrator/analyzer.py`
2. Add to `DEFAULT_PERSPECTIVES` dict:

```python
DEFAULT_PERSPECTIVES = {
    # ... existing ...
    "custom": """
        Analyze from a custom perspective.
        Focus on: [specific concerns]
        Report: [expected output format]
    """,
}
```

### Modify plan execution

1. Edit `src/orchestrator/executor.py`
2. Adjust step execution logic or add new step types

## Usage Example

```python
# Multi-step plan
result = execute_plan(
    goal="Refactor authentication module",
    steps=[
        {"description": "Analyze current auth flow", "tool": "analyze_parallel", "expected_output": "Flow diagram"},
        {"description": "Identify security issues", "tool": "spawn_specialist", "expected_output": "Vulnerability list"},
        {"description": "Propose refactoring", "tool": "spawn_specialist", "expected_output": "Refactoring plan"},
    ]
)

# Parallel analysis
analysis = analyze_parallel(
    code=file_contents,
    perspectives=["security", "performance", "architecture"]
)
```
