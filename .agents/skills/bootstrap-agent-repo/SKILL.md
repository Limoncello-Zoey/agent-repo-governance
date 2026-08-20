---
name: bootstrap-agent-repo
description: Initialize or retrofit an existing software repository for Agent-oriented development and checkpoint maintenance. Use when a user asks to bootstrap, standardize, or establish AGENTS.md, semantic documentation routing, task-state conventions, and the peer checkpoint Skills. Initialization never changes business/source/test code or commits Git history.
---

# Bootstrap an Agent-Friendly Repository

Establish the minimum durable Agent guidance for an existing repository. This Skill is intentionally complete because initialization both reads the repository and writes the initial Agent-facing structure. Adapt to repository evidence; do not impose a generic platform.

## Design philosophy

The infrastructure has two work surfaces:

- **Read documents, write code:** the main Agent reads the project map, high-frequency rules, and routed domain knowledge; modifies engineering code and tests; and discusses scope and risk with the user. During ordinary development it does not maintain documentation or Git checkpoint details.
- **Read code, write documents, save Git:** a checkpoint child Agent reviews the frozen code diff, updates semantic indexes and interface documents, and performs all staging, commit, verification, and lock cleanup.

The main Agent needs an index and a cheap route to information, not the full maintenance-writing manual. The child receives that manual through the independent, peer `$checkpoint-maintenance` Skill. `$save-checkpoint` is only the main Agent's short dispatch protocol; it is not a parent Skill.

Keep knowledge in the right layer:

- `AGENTS.md`: verified project map, high-frequency rules, canonical commands, safety boundaries, definition of done, and the shortest routes to deeper knowledge.
- Project docs: project facts, architecture, flows, domain decisions, interfaces, and runbooks.
- Skills: repeatable workflows that require judgment, including initialization and checkpoint maintenance.
- Scripts: small deterministic helpers only when repeated mechanical execution justifies them.
- Task state: temporary branch/task handoff, never the long-term authority.

Routing has a cost in tokens, Agent turns, context, waiting time, and misrouting risk. Put a rule directly in `AGENTS.md` only when it is frequent and consequential. Route low-frequency maintenance details through Skill-internal references instead of making the main Agent read them on every task.

## Safety and initialization boundary

- Inspect before editing and preserve existing instructions, docs, skills, configuration, and user changes.
- Do **not** modify business code, source code, tests, generated runtime logic, dependencies, or project behavior during bootstrap.
- Do **not** commit, push, switch branches, rebase, merge, or rewrite Git history during bootstrap.
- It is allowed to create or update the minimum `AGENTS.md`, project documentation indexes/routes, task-state convention, and Skill files required for this Agent infrastructure.
- Do not copy or “unpack” this general philosophy into project docs. It remains inside the installed Skills. Existing `docs/agent-development-workflow.md` or similar user documentation must be preserved unless the user explicitly requests migration; do not generate another copy automatically.
- Do not add secrets, machine-specific absolute paths, MCP servers, Hooks, CI, or complex automation without repository evidence or explicit user intent.

## 1. Inspect, then classify

Resolve this Skill's own directory from the loaded `SKILL.md`. The bundled `scripts/inspect_repo.py` is an optional read-only inventory aid, not an authority and not a replacement for reading files:

```bash
python3 <skill-dir>/scripts/inspect_repo.py <repository-root>
```

Read the actual manifests, task runners, CI, root docs, existing `AGENTS.md`, Skill files, and relevant history. Use `rg --files` and targeted `rg`; avoid dependency, generated, and cache trees. Treat `.gitignore` as an important scan hint when present, while retaining explicit safety exclusions for VCS metadata, dependencies, and generated output. Never infer an ecosystem merely from an extension count.

Read [references/target-state.md](references/target-state.md), compare it with repository evidence, and classify each target as adequate, incrementally updateable, useful now, or intentionally omitted. Ask only when an existing policy conflicts or a choice materially changes project behavior.

## 2. Establish the minimum target state

### Root Agent guidance

Create or refine the root `AGENTS.md` as a concise, factual router. Include only verified project structure and commands, high-frequency coding/testing expectations, safety rules, definition of done, and the shortest documentation/Skill entry points. Merge with non-empty existing content; never replace it blindly. Add nested `AGENTS.md` only where a subtree has genuinely different rules.

At minimum, route:

- ordinary engineering work to the project docs and local rules;
- initialization requests to `$bootstrap-agent-repo`;
- “存一版”/checkpoint requests to `$save-checkpoint`;
- checkpoint details to the child-only `$checkpoint-maintenance` Skill.

### Semantic documentation

Choose one authoritative root-level `docs`, `documentation`, or `doc` directory case-insensitively, preserving its on-disk spelling. If several exist, identify one authoritative entry rather than silently combining them. Do not move a large legacy collection blindly.

Default to two directory levels:

```text
docs/
├── INDEX.md
└── <module>/
    ├── INDEX.md
    └── <submodule>.md
```

Each index explains its scope/boundary, immediate children and layering, runtime entry, primary information/control/data flow, and semantic routes. A leaf document is for an independently meaningful module, interface, runtime boundary, or cross-module contract—not for every function, class, or source file. Document verified inputs, outputs, constraints, errors, dependencies, lifecycle, and at least one evidence-backed invocation example. Review indexes on checkpoints, but edit them only when structure, entry points, flows, boundaries, or preferred routes change.

Add `last_reviewed_commit_title` only to authoritative documents actually reviewed. During bootstrap it is normally `null`; do not touch every Markdown file.

### Task state and peer Skills

Create a task/branch state template only when work regularly spans sessions or people and no established tracker exists. Keep it temporary and promote durable facts into normal docs or ADRs.

Verify that the peer Skills are available:

- `.agents/skills/save-checkpoint/SKILL.md` for main-Agent dispatch;
- `.agents/skills/checkpoint-maintenance/SKILL.md` for child maintenance.

If a peer is missing, report the gap. Do not silently duplicate its workflow into this Skill or invoke it during bootstrap unless the user separately asks to commit.

## 3. Conservative automation

Prefer existing project commands, then a small deterministic helper, then a Skill for judgment-heavy repetition. Keep `inspect_repo.py` read-only and conservative; it may list files, manifests, docs, and Git facts but must not generate docs, discover “the ecosystem,” or decide what to skip semantically. Keep checkpoint locking/tree verification in the checkpoint helper. Do not encode module-impact, document wording, atomicity, or conflict-resolution judgments in scripts.

## 4. Validate and report

After editing, rerun the optional inventory and verify:

1. No business/source/test/runtime files changed.
2. Every command in `AGENTS.md` is evidenced by the repository.
3. The authoritative docs root and relevant module directories have concise indexes and resolving relative links.
4. Reviewed leaf docs contain real invocation evidence; no template placeholders remain.
5. New/edited files pass `git diff --check` when a Git worktree exists.
6. No unrelated user changes, secrets, or machine-local paths were overwritten or added.

Leave changes uncommitted unless the user explicitly requested a commit. Report files changed, verified entry points, omitted optional infrastructure, peer Skill availability, unresolved uncertainties, and the next checkpoint invocation (`$save-checkpoint` or “存一版”).
