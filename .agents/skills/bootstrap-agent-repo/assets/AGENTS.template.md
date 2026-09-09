# Repository Guidelines

## Project Map

- `{{source-path}}`: {{source-purpose}}
- `{{test-path}}`: {{test-purpose}}
- `{{docs-path}}`: project knowledge; start with `{{docs-index}}`

## Canonical Commands

- `{{setup-command}}`: install or prepare dependencies.
- `{{test-command}}`: run the relevant automated tests.
- `{{lint-command}}`: run formatting and static checks.
- `{{run-command}}`: start the project locally.

Include only commands verified in manifests, task runners, CI, or existing documentation. Remove unavailable command categories.

## Working Agreements

- Preserve unrelated user changes in a dirty worktree.
- Keep generated files synchronized with their sources.
- Add tests for behavior changes and regression fixes.
- Do not add secrets, credentials, or machine-specific paths.

## Documentation Routing

- Keep the authoritative documentation tree under the root-level `{{docs-path}}` directory.
- Read `{{docs-index}}`, then the affected first-level module's `INDEX.md`, before changing architecture, domain behavior, operations, data flow, or interfaces.
- Use the default two-level layout: root `INDEX.md`, one directory and `INDEX.md` per functional module, and one `<submodule>.md` per independently documentable child module.
- Document each leaf module's interface and verified invocation method, including inputs, outputs, errors, and dependencies; do not create one document per function or source file.
- Review affected level indexes at checkpoint time; edit them only when module structure, flow, document location, or semantic boundaries change.
- Use task-scoped state notes only for temporary handoffs; promote durable knowledge into normal documents or ADRs.

## Checkpoint Commits

Use `$save-checkpoint` or the phrase “存一版” for a staged-snapshot checkpoint. The main Agent freezes and delegates; the child explicitly uses `$checkpoint-maintenance` for documentation and Git operations. During that workflow, the main Agent may keep editing unstaged source files but must not modify the Git index, documentation owned by the checkpoint Agent, branch state, or commit history.

## Definition of Done

- Relevant tests and checks pass or exceptions are reported.
- Architecture, interface, invocation, and generated documentation reflect the change.
- The final diff contains no unrelated files or unresolved placeholders.

## Repository governance policy

When configured, `.agents/repo-governance.json` records this project's protected
branches and external source directories. Registered trees are checked against
`.agents/external-code.snapshot.json` on checkpoints; changes require semantic review
before accepting a baseline. Only include this route when those files are established.
