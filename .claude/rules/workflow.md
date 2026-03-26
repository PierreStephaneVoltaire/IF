### Workflow

- **Plan first**: For coding tasks, explore the codebase first, understand existing patterns, identify affected files, then produce a step-by-step implementation plan before touching code. Only proceed when the operator confirms, or explicitly asks to skip.
- **Read before modifying**: Do not propose changes to code you have not read. If asked to modify a file, read it first. Understand existing code before suggesting modifications.
- **Reversibility**: Consider the reversibility and blast radius of every action. Freely take local, reversible actions (editing files, running tests). Confirm before destructive operations (deleting files, force-push, dropping tables, overwriting uncommitted changes).
- **Adopt code style**: When the operator's preferred language, framework, or style conventions become apparent, adopt them. Mirror their patterns unless doing so violates a higher directive.
