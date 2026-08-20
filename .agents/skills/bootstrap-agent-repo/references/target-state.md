# Target State Reference

Use this reference to decide what an existing repository needs. It defines a minimum viable management system, not a mandatory directory template.

## Minimum target

### 1. Durable repository guidance

The root `AGENTS.md` should answer, using verified project facts:

- What are the major source, test, asset, generated, and documentation areas?
- Which commands install, build, run, format, lint, and test the project?
- Which checks are required after common changes?
- Which files or actions are sensitive, generated, destructive, or externally visible?
- Where should an Agent read deeper architecture, domain, runbook, or decision knowledge?
- What constitutes a completed change?

Keep explanations concise. Put detailed architecture and procedures in documents or skills. Do not duplicate entire READMEs.

### 2. Two-level architecture documentation

Keep the authoritative documentation collection in one directory directly under the repository root. Discover `docs`, `documentation`, and `doc` case-insensitively and preserve the actual spelling already used; otherwise prefer `docs/`. If multiple candidates coexist, choose and document one authoritative root. A root entry may link to legacy material during gradual migration, but the long-term knowledge tree should not remain scattered across the repository.

Organize the tree by functional modules rather than by a mechanical copy of source paths. The default has exactly two directory levels:

```text
docs/
├── INDEX.md
└── <module>/
    ├── INDEX.md
    └── <submodule>.md
```

The root `INDEX.md` routes project-level knowledge and first-level modules. Each module `INDEX.md` describes that module and routes its child-module leaf files. Do not add deeper module directories unless the real architecture or an explicit user requirement cannot be represented clearly in this layout; record the reason when doing so.

Each level index stays concise and communicates:

- the module or level purpose, boundary, and responsibilities;
- its immediate child modules and their layering or dependency relationships;
- how that level is initialized, started, entered, or operated;
- the principal information, control, and data flow through the level;
- semantic routes to child indexes and leaf documents;
- exclusions that belong to neighboring modules.

The same `INDEX.md` serves as both the level architecture overview and the semantic routing entry. Do not maintain a separate code-path-to-document matrix.

Review relevant indexes during each checkpoint but edit them only when:

- a module or document is added, removed, renamed, split, or merged;
- child layering, dependencies, responsibilities, or semantic boundaries change;
- runtime entry points or major information/data flows change;
- the preferred reading entry for a topic changes.

Do not update parent indexes for ordinary implementation corrections inside an unchanged module boundary.

### 3. Leaf module interfaces

A leaf node describes a child module with an independent architectural responsibility, interface, runtime boundary, or cross-module call contract. By default it is a named Markdown file inside a first-level module directory. Do not create one document per function, class, or source file. A terminal directory `INDEX.md` is reserved for an explicitly justified deeper hierarchy.

Every leaf module document includes, when applicable:

- purpose, responsibilities, and explicit exclusions;
- prerequisites, initialization, runtime lifecycle, and shutdown;
- callers, dependencies, outputs, and the local data-flow path;
- public or internal interfaces and the actual way to invoke them;
- inputs and outputs with types, schemas, units, constraints, and defaults;
- error behavior and, where relevant, timeout, retry, idempotency, and compatibility semantics;
- at least one invocation example verified against repository evidence.

Interfaces include functions, classes, HTTP/RPC APIs, CLI commands, events, message topics, file formats, configuration keys, plugin entry points, hardware links, and process boundaries. If no public interface exists, document the internal entry point and state that external callers must not depend on it.

### 4. Document validity

An authoritative document may record the title of the commit in which its content was last intentionally updated or semantically reviewed:

```yaml
---
last_reviewed_commit_title: "feat(auth): 支持设备授权流程"
---
```

During initial bootstrap, use `null` until the first checkpoint title is frozen. Add the field only to documents actually reviewed. If frontmatter would break the current documentation system, use:

```md
> 最后语义校验提交：尚未提交
```

This is a semantic freshness signal, not a unique Git identifier. Do not repeat it in the semantic index. Pure formatting changes should not imply a new semantic review.

### 5. Task state

Use task- or branch-specific notes only when work regularly spans sessions or people. A useful task state contains:

- task identifier and goal;
- base branch or relevant baseline;
- completed work;
- next actions;
- blockers and unresolved decisions;
- verification already performed.

Promote durable facts into normal documents or ADRs before closing the task. Avoid one shared, append-only root `MEMORY.md`, which becomes a merge-conflict and stale-information hotspot.

### 6. Checkpoint workflow

Initialization and maintenance are peer lifecycle concerns. `bootstrap-agent-repo` establishes the repository structure and conventions; the independent `save-checkpoint` Skill dispatches the recurring checkpoint; and the independent `checkpoint-maintenance` Skill performs documentation synchronization and Git operations. None of the three is nested inside or packaged as an asset of another.

The peer checkpoint Skills should implement this boundary:

- the Git index holds the frozen commit snapshot;
- `.git/agent-checkpoint.lock` records the base HEAD, branch, frozen title, and initial staged entries;
- the main Agent may continue editing unstaged source files;
- the checkpoint Agent owns staging, documentation updates, and the commit;
- the main Agent must not stage, reset, stash, commit, rebase, or switch branches until the checkpoint Agent finishes;
- both Agents avoid overlapping edits to the same documentation.

After receiving `snapshot_frozen`, the checkpoint Agent explicitly invokes `$checkpoint-maintenance`, verifies the lock and initial staged entries, reads `git diff --cached`, checks architecture, runtime, flow, and interface impact, and follows `INDEX.md → <module>/INDEX.md → <module>/<submodule>.md`. It updates affected documents and validity markers, writes a detailed Simplified Chinese body, seals the final index with `git write-tree`, commits, verifies `HEAD^{tree}` against the sealed tree, removes the lock, and returns `checkpoint_done`. If sub-agents are unavailable, the workflow may run serially but must announce that downgrade.

### 7. Reusable operations

Prefer these layers in order:

1. Existing project commands and task runners.
2. A small repository script for repeated deterministic operations.
3. A focused Skill for a repeated workflow requiring judgment.
4. Hooks only for cheap, mechanical enforcement.
5. MCP only for authenticated live external data or actions.

Do not create empty infrastructure directories solely to match a diagram.

## Optional components

Add the following only with project evidence or explicit user intent:

- `.codex/config.toml`: project-scoped Codex behavior in a trusted repository.
- Hooks: staged-diff checks, secret scanning, or lifecycle enforcement that has proved necessary.
- MCP: GitHub, issue tracking, documentation services, design systems, or internal platforms.
- A separate multi-Skill distribution repository and installer: useful when these peer Skills are shared as one installation unit; do not turn them into a parent Skill or require a Plugin manifest.
- CI checks for Agent assets: only after manual conventions repeatedly drift.

## Migration rules

- Preserve existing instructions and contributor conventions unless they conflict or are demonstrably stale.
- Treat a dirty worktree as user-owned. Edit overlapping files carefully and never discard changes.
- Keep framework-specific documentation structure when it already works.
- Prefer updating one authoritative source and linking to it over creating competing documents.
- Explain omissions in the final handoff so absence is intentional rather than accidental.
