# AgentSkills Directory

This directory contains AgentSkills-compliant skill packages. Skills are loaded
per-specialist at spawn time — the main agent does not load skills globally.

## Layout

```
skills/
└── <skill-name>/
    ├── SKILL.md              # Required: YAML frontmatter + markdown body
    ├── scripts/              # Optional: executable code (run via uv/uvx/npx)
    ├── references/           # Optional: on-demand reference docs
    └── assets/               # Optional: templates/data
```

## SKILL.md Format

```markdown
---
name: my-skill
description: Brief description of what this skill does (shown in skill catalog)
compatibility: Python 3.12+ and uv  # Optional
---

# Skill Title

## When to use
Describe the scenarios where this skill should be activated.

## How to run
Instructions for executing skill scripts (e.g., `uv run --project skills/my-skill python scripts/main.py`).

## References
- Link to relevant docs or resources
```

## Usage in Specialists

Add a `skills:` field to `specialist.yaml`:

```yaml
description: Code generation and debugging
tools: [terminal_execute, read_file, write_file]
preset: "@preset/code"
agentic: true
skills: [git-workflows, testing-patterns]  # Skills this specialist uses
```

## Execution

Skill scripts run via the specialist's terminal tools:

- **Python skills**: `uv run --project skills/<name> python scripts/<script>.py`
- **Node skills**: `npx -y <package>@latest` or `npm run --prefix skills/<name> <script>`

Scripts execute in isolated uv-managed venvs, same as temporal_* tool plugins.

## Spec

See [agentskills.io](https://agentskills.io/specification) for the full AgentSkills specification.
