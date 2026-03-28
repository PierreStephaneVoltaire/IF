# Design: Git PR Review Specialist

## Problem

IF has no awareness of the operator's code repositories. When the operator asks "can you review the PR I just opened?" or "what changed in the last commit?", the agent has no tools to access git history, diffs, or PR metadata.

The operator has explicitly scoped this to **read-only review** — no pushing commits, no writing code to the repo. Tools like Claude Code and OpenHands already do the writing better. IF's value here is as a reviewer with persistent memory: it knows the operator's architecture preferences, past decisions, coding conventions (stored as user facts), and can apply that context to reviews.

## Scope

- **PR review**: Fetch diff, analyze changes, provide structured feedback
- **Commit inspection**: Read commit history, understand what changed
- **Branch comparison**: Diff two branches
- **Repository awareness**: Clone/fetch repos the operator works on

**Explicitly out of scope:**
- Pushing commits or creating PRs
- Writing code fixes (the operator uses other tools for that)
- CI/CD integration
- Issue/ticket management (the `jira_writer` specialist handles that)

## Architecture Fit

New specialist: `code_reviewer`

```
src/agent/prompts/specialists/code_reviewer.j2
```

Registered in `src/agent/specialists.py`:

```python
"code_reviewer": SpecialistConfig(
    description="Git-aware code review with project context",
    directive_types=["code", "architecture"],
    mcp_servers=[],  # Uses terminal tools for git access
)
```

### Git Access via Terminal

IF already has terminal access in persistent Docker containers. Git operations run through `terminal_execute`:

```python
terminal_execute("git clone https://github.com/user/repo.git /home/user/repos/repo")
terminal_execute("git -C /home/user/repos/repo fetch origin")
terminal_execute("git -C /home/user/repos/repo diff origin/main...origin/feature-branch")
```

This means:
- No new MCP server needed
- Repos persist in the terminal container's volume
- Git credentials need to be available in the container (see Config section)

### GitHub API for PR Metadata

For PR-specific operations (comments, review status, CI results), use the GitHub API directly via terminal:

```bash
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}
```

Or add a lightweight GitHub MCP server. The operator can decide based on how much PR interaction they want.

## Workflow: Fetch → Understand → Review → Report

### PR Review Flow

```
TRIGGER: Operator asks to review a PR
  - "Review PR #42 on my-repo"
  - "What do you think of the latest PR?"
  - Main agent delegates to code_reviewer specialist

Step 1: FETCH
  - Determine repo and PR number from operator request
  - If repo not cloned: git clone (with depth=1 for speed)
  - If repo exists: git fetch origin
  - Get PR diff: git diff origin/main...origin/{pr_branch}
  - Get PR metadata via GitHub API (title, description, files changed, CI status)
  - Get commit list on the PR branch

Step 2: UNDERSTAND (context assembly)
  - Read the diff
  - For each changed file, read the full file for surrounding context
  - Pull relevant user facts:
    - Project conventions (preference facts)
    - Architecture decisions (project_direction facts)
    - Past opinions on patterns used in this PR
    - Known problem areas (if any)
  - Identify: what is this PR trying to do?

Step 3: REVIEW (structured analysis)
  Apply review from these perspectives:

  a. CORRECTNESS
     - Does the code do what the PR description says?
     - Are there logic errors, off-by-ones, missing edge cases?
     - Are error paths handled?

  b. CONVENTIONS
     - Does it follow the operator's known coding conventions?
     - Naming consistency with the rest of the codebase?
     - File organization matching project patterns?

  c. ARCHITECTURE
     - Does this change fit the existing architecture?
     - Does it introduce new patterns that conflict with established ones?
     - Dependency concerns?

  d. RISK
     - What could break?
     - Are there missing tests for critical paths?
     - Any security concerns?

  Calibration (from Superpowers review methodology):
  - Only flag issues that cause REAL problems
  - Do not block on style preferences unless they violate stated conventions
  - If something looks intentional, ask rather than flag

Step 4: REPORT
  Structured output:

  ## PR Review: {title}

  **Summary**: {one-line summary of what the PR does}
  **Verdict**: APPROVE / REQUEST_CHANGES / NEEDS_DISCUSSION

  ### Key Findings
  - {finding 1 — with file:line reference}
  - {finding 2}

  ### Convention Notes
  - {any convention violations, referencing stored preferences}

  ### Questions
  - {things that look intentional but warrant confirmation}

  ### Risk Assessment
  - {what could go wrong, severity}

  If write_to_file specified, save to file. Otherwise return inline.
```

### Commit Inspection Flow

```
TRIGGER: "What changed in the last 3 commits?" / "Show me what feature-x branch has"

Step 1: FETCH
  - git log --oneline -N
  - For each commit: git show {hash} --stat
  - For detailed view: git show {hash}

Step 2: SUMMARIZE
  - Group changes by area/module
  - Note: new files, deleted files, significant refactors
  - Flag anything that looks risky or inconsistent

Step 3: REPORT
  Structured commit summary with links to specific changes.
```

## Specialist Template Sketch: `code_reviewer.j2`

```jinja2
You are a code review specialist with access to git repositories via terminal tools.

## Directives
{{ directives }}

## Operator Context
{{ operator_context }}

## Task
{{ task }}

## Context
{{ context }}

## Tools Available
- terminal_execute: Run git commands, curl GitHub API
- terminal_read_file: Read source files for full context
- terminal_list_files: Navigate repository structure
- user_facts_search: Retrieve operator conventions and preferences

## Review Methodology

### Calibration Rules
- Only flag issues that cause real implementation problems
- Style preferences are NOT blocking unless they violate stated operator conventions
- If something looks intentional, ask — don't flag
- Max 10 findings per review (prioritize by severity)
- Be specific: file, line number, what's wrong, what to do instead

### Review Structure
For every PR review, produce:
1. One-line summary of what the PR does
2. Verdict: APPROVE / REQUEST_CHANGES / NEEDS_DISCUSSION
3. Key findings (blocking issues)
4. Convention notes (non-blocking)
5. Questions (things to clarify)
6. Risk assessment

### Git Access Pattern
- Always fetch before diffing (repos may be stale)
- Use `git diff origin/main...origin/{branch}` for PR diffs (three dots for merge-base)
- Read full files for context, not just diff hunks
- Use `--stat` for overview before diving into details

### Operator Knowledge
Before reviewing, search user_facts for:
- query: "{repo_name} conventions"
- query: "{language} preferences"  
- query: "architecture decisions"
- category: preference
- category: project_direction

Apply stored conventions to the review. If the PR follows a convention
the operator has explicitly stated, do not flag it even if you disagree.

<HARD-GATE>
Do NOT suggest code changes or write fixes.
Do NOT push to the repository.
Do NOT approve PRs without actually reading the diff.
If the diff is too large to review meaningfully (>2000 lines changed),
say so and suggest reviewing by file group or commit.
</HARD-GATE>
```

## Repository Management

### First-Time Setup

When the operator first asks about a repo:

```
1. Clone with depth=1: git clone --depth=1 {repo_url} /home/user/repos/{repo_name}
2. Store as user fact: "Operator works on {repo_name} at {repo_url}"
   category: project_direction, source: user_stated
3. Optionally: scan repo structure, identify language, framework, test setup
   Store findings as project_direction facts
```

### Ongoing Access

```
- git fetch origin before any review
- Shallow clone keeps disk usage manageable
- If operator works on many repos, track them as facts for quick access
- Terminal container volumes persist between sessions
```

### Credentials

Git credentials in the terminal container. Two options:

**Option A: GitHub token in terminal env**
```bash
# Set in terminal container at startup
git config --global credential.helper '!f() { echo "username=token"; echo "password=$GITHUB_TOKEN"; }; f'
```

**Option B: SSH key mounted in terminal volume**
```bash
# SSH key persisted in terminal volume
/home/user/.ssh/id_ed25519
```

The operator configures this once. The token/key lives in the terminal container, not in IF's main process.

## New Modules

| File | Purpose |
|------|---------|
| `src/agent/prompts/specialists/code_reviewer.j2` | Code review specialist template |

## Changes to Existing Modules

| File | Change |
|------|--------|
| `src/agent/specialists.py` | Register `code_reviewer` specialist |

## Config

| Variable | Default | Description |
|----------|---------|-------------|
| `CODE_REVIEWER_MAX_DIFF_LINES` | `2000` | Max diff lines before suggesting chunked review |
| `CODE_REVIEWER_MAX_FINDINGS` | `10` | Max findings per review |
| `GITHUB_TOKEN` | - | GitHub personal access token (set in terminal container) |
| `GIT_REPOS_PATH` | `/home/user/repos` | Where repos are cloned in terminal container |

## Future Extensions (out of v1 scope)

1. **GitHub MCP server**: Richer PR interaction — post review comments directly on GitHub, approve/request changes via API, read CI results.

2. **Auto-review on PR open**: Webhook from GitHub → IF channel → auto-dispatch code_reviewer. Requires a new channel listener type.

3. **Review memory**: After reviewing a PR, store findings as facts. Next time the same file is modified, reference past review comments. "Last time this file was changed, I flagged X — was that resolved?"

4. **Multi-repo awareness**: Cross-repo review when the operator's repos depend on each other. "This change in repo-A will break the API contract used by repo-B."

5. **GitLab/Bitbucket**: Same patterns, different API. The git CLI parts are universal; only the API calls for PR metadata differ.

## Open Questions

1. **Repo discovery**: Should the agent proactively ask what repos the operator works on during pondering/learn sessions? Or wait until they ask for a review?

2. **Large PRs**: The 2000-line threshold is arbitrary. Should we offer chunked review by file group, by commit, or by module? Probably by commit is most useful since each commit should be a logical unit.

3. **Review style**: Should the specialist adapt its review depth based on the operator's seniority? A senior dev wants "here are the risks" not "here's how a for loop works." The operator's `skill` facts could drive this.

4. **Diff format**: `git diff` output can be large. Should we pre-process it to extract only the meaningful changes (skip lock files, generated code, etc.)? A `.gitattributes`-aware filter would help.

5. **Integration with existing specialists**: Should the code_reviewer be able to delegate to `secops` for security-specific review, or `architect` for design review? Parallel specialist dispatch (`spawn_specialists(["code_reviewer", "secops"], ...)`) already supports this at the main agent level.
