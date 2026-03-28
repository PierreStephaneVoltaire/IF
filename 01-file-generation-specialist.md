# Design: File Generation Specialist

## Problem

IF's main agent has terminal access (`terminal_write_file`, `terminal_execute`) but no structured workflow for producing files. When the operator says "write me a bash script" or "generate a Terraform module", the main agent either:

1. Dumps code inline in the chat (no file artifact)
2. Uses `terminal_write_file` ad hoc with no verification step
3. Generates via `terminal_execute` with heredocs or echo chains (brittle, escaping issues)

None of these guarantee the output is syntactically valid, runnable, or matches what was asked for. The Superpowers `verification-before-completion` skill exists because LLMs routinely declare success without checking their work.

## Scope

This covers **code and config file generation** — scripts, modules, configs, IaC, dockerfiles, markdown documents. It does NOT cover document formats like DOCX/PDF/PPTX (those would be separate specialists with format-specific tooling).

## Architecture Fit

New specialist: `file_generator`

```
src/agent/prompts/specialists/file_generator.j2
```

Registered in `src/agent/specialists.py`:

```python
"file_generator": SpecialistConfig(
    description="Structured file generation with validation",
    directive_types=["code", "architecture"],
    mcp_servers=[],
)
```

The main agent delegates via existing `spawn_specialist`:

```python
spawn_specialist(
    specialist_type="file_generator",
    task="Generate a Terraform module for an ECS Fargate service",
    context="Uses AWS provider 5.x, existing VPC in module.vpc_id",
    write_to_file="sandbox/{conversation_id}/ecs-fargate/main.tf"
)
```

## Workflow: Generate → Validate → Verify → Deliver

This is a **deterministic pipeline**, not a suggestion to the LLM. The specialist template enforces gates.

```
Step 1: PLAN
  - Parse the request into: language, output path(s), purpose, constraints
  - If ambiguous, ask ONE clarifying question (max 1 round)
  - Produce a file manifest: what files, what each contains, dependencies

Step 2: GENERATE
  - Write each file via terminal_write_file
  - One file at a time, complete content (no partial writes)

Step 3: VALIDATE (language-specific, deterministic)
  - Python: python -m py_compile {file}
  - JavaScript/TypeScript: node --check {file} / npx tsc --noEmit
  - Bash: bash -n {file}
  - Terraform: terraform fmt -check && terraform validate
  - YAML: python -c "import yaml; yaml.safe_load(open('{file}'))"
  - JSON: python -m json.tool {file}
  - Dockerfile: hadolint {file} (if available, else skip)
  - Markdown: no validation needed
  - Unknown: skip validation, note it in output

  If validation FAILS:
    - Read the error
    - Fix the file
    - Re-validate
    - Max 3 fix attempts, then surface error to operator

Step 4: VERIFY (content check)
  - Re-read the generated file(s) via terminal_read_file
  - Compare against original request: does it actually do what was asked?
  - Check for: hardcoded values that should be params, missing error handling,
    TODO/placeholder comments left in, incomplete implementations

Step 5: DELIVER
  - Return: file path(s), what was generated, validation status
  - If files are in sandbox, they're accessible via /files/sandbox/{conv_id}/
```

### Gate Enforcement

The specialist template must include hard gates:

```
<HARD-GATE>
Do NOT report completion until:
1. Every file has been written to disk
2. Every file that CAN be validated HAS been validated (syntax check passed)
3. You have re-read every file and confirmed it matches the request
Skipping any of these steps is a critical failure.
</HARD-GATE>
```

## Template Sketch: `file_generator.j2`

```jinja2
You are a file generation specialist. You produce files that are correct, complete, and validated.

## Directives
{{ directives }}

## Task
{{ task }}

## Context
{{ context }}

## Tools Available
- terminal_write_file: Write file content
- terminal_read_file: Read file content back
- terminal_execute: Run validation commands
- terminal_list_files: Check output directory

## Workflow (MANDATORY — follow in order)

### 1. PLAN
Determine: language(s), output path(s), purpose, constraints.
Produce a file manifest before writing anything.

### 2. GENERATE
Write each file completely via terminal_write_file.

### 3. VALIDATE
Run language-appropriate syntax validation on every generated file.
Fix failures (max 3 attempts per file). If unfixable, report the error.

Validation commands by language:
- Python: `python -m py_compile {path}`
- JavaScript: `node --check {path}`
- TypeScript: `npx tsc --noEmit --allowJs {path}`
- Bash/Shell: `bash -n {path}`
- Terraform: `terraform fmt -check -diff {path} && terraform validate`
- YAML: `python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" {path}`
- JSON: `python3 -m json.tool {path} > /dev/null`

### 4. VERIFY
Re-read every file. Confirm it matches the request. Check for:
- Hardcoded values that should be parameters
- TODO/placeholder comments
- Missing error handling
- Incomplete implementations

### 5. DELIVER
Report: paths, what each file does, validation status.

<HARD-GATE>
Do NOT report success until steps 1-4 are complete.
Do NOT skip validation for any file that has a syntax checker available.
If you cannot validate, explicitly state why.
</HARD-GATE>
```

## New Modules

| File | Purpose |
|------|---------|
| `src/agent/prompts/specialists/file_generator.j2` | Specialist template |

Changes to existing modules:

| File | Change |
|------|--------|
| `src/agent/specialists.py` | Register `file_generator` in specialist registry |

## Config

| Variable | Default | Description |
|----------|---------|-------------|
| `FILE_GEN_MAX_FIX_ATTEMPTS` | `3` | Max validation fix cycles per file |

## Open Questions

1. **Should the main agent auto-delegate to this specialist?** Or should it only fire when the operator explicitly asks for file generation? A directive could handle this: "When the operator requests file creation, delegate to `file_generator` specialist."

2. **Multi-file projects**: Should the manifest step produce a dependency order (e.g., types file before implementation file)? Probably yes for TypeScript projects.

3. **Template files**: Should the specialist have access to project-specific templates (e.g., the operator's preferred Terraform module structure)? Could be stored as user facts or in the sandbox.

4. **Sandbox vs terminal**: Currently files go to the terminal container's filesystem. Should generated files also be copied to `sandbox/{conversation_id}/` for HTTP serving? Probably yes for delivery.
