# Checkpoint Maintenance Philosophy

This document is internal to `checkpoint-maintenance`. It is intentionally not copied into project documentation and is not part of the main Agent's normal routing context.

## 1. Two work surfaces and authority

The main Agent reads project knowledge and writes engineering changes. The checkpoint child reads the resulting code and writes durable knowledge, then stores a verified Git version. This is a division of responsibility, not a claim that code and documentation are unrelated: the child updates docs only when the frozen code changes their facts, routes, interfaces, or semantic validity.

The project docs describe project facts. This Skill describes the reusable maintenance method. `AGENTS.md` is a high-frequency router, not a second copy of this philosophy. If a project document and this generic method conflict, preserve project-specific facts and report the conflict rather than silently rewriting them.

## 2. Atomic change

An atomic change is one user-intent slice that can be explained and verified independently. It is not one file, one class, or one document. A single commit may contain code, tests, configuration, affected indexes, leaf interface docs, and validity markers when they belong to the same user intent. Split or ask only when the staged diff combines genuinely unrelated goals or would require different release/rollback decisions.

## 3. Documentation model

Use the smallest useful semantic tree:

```text
documentation root INDEX.md
└── module INDEX.md
    └── submodule leaf.md
```

Indexes are maps, not exhaustive implementation records. They state scope, boundaries, immediate children, layering/dependencies, runtime entry, primary information/control/data flow, and routes to deeper knowledge. Edit an index only when one of those facts changes. Do not create a code-path-to-document matrix.

Leaf documents cover independently meaningful modules, runtime boundaries, or cross-module contracts. They must use repository evidence to state purpose and exclusions, lifecycle, callers and dependencies, interface and actual invocation, inputs/outputs/types/units/defaults, constraints, errors, timeout/retry/idempotency/compatibility semantics where applicable, and at least one call example. Do not create a document for every function or source file merely because it exists.

Review routing from the root index to the affected module index, then use targeted searches. Routing is deliberately selective: every extra document read costs tokens, turns, context, waiting time, and opportunities for wrong assumptions. Read a low-frequency reference only when the frozen change makes it relevant.

## 4. Validity markers

For each authoritative document that was materially updated or semantically checked, set:

```yaml
last_reviewed_commit_title: "<frozen title>"
```

The marker records the semantic checkpoint title, not a unique commit identifier. Do not touch unrelated documents or claim semantic review for whitespace-only edits. The title is frozen before delegation and must remain identical in the final commit subject and updated markers.

## 5. Frozen index protocol

The initial staged index is a concurrency boundary:

1. `freeze` records base `HEAD`, branch, title, and every initially staged path/mode/blob.
2. `verify` confirms those facts before takeover.
3. The main Agent may create later unstaged source edits, but they are not this checkpoint.
4. The child may add or restage its own maintenance docs after takeover. It must not rerun the initial snapshot check after legitimate doc restaging.
5. The child reviews the whole final staged diff, runs staged whitespace checks, and confirms no later source work, secret, temporary file, or unrelated change entered the index.
6. `seal` records the complete final index tree immediately before commit.
7. `verify-commit --clear` requires the new commit's tree to equal the sealed tree and its sole parent to equal the frozen base `HEAD`; only then is the lock removed.

If any identity, index, branch, parent, or tree invariant fails, stop. Do not reset, stash, rebase, or “fix” the repository by guesswork.

## 6. Branch and history neutrality

Support ordinary, feature, release, development, and otherwise unusual branch names. Use the currently checked-out branch unless the user explicitly requests another operation. A checkpoint commit normally has the frozen `base_head` as its sole parent, whether that base is a normal commit or a merge commit. Do not assume a single-line history. Branch switching, rebase, merge, and other history operations require explicit user intent and remain under the delegated child's Git ownership.

## 7. Commit message and verification

The frozen subject is a semantic Simplified Chinese result, following an existing project convention when one is evidenced. The body should distinguish:

```text
<frozen title>

变更内容：
- ...

文档更新：
- ...

验证情况：
- ...
```

Report tests accurately. Tests run after concurrent work begins may observe unstaged changes; do not present them as proof of the frozen snapshot unless isolation was actually used. Prefer the project's existing checks; do not invent commands.

## 8. Merge preview boundary

The main Agent performs a read-only `git merge` preview because it owns user-facing explanation and confirmation. The child executes only after the preview is understood: no-conflict previews can be handed off directly; conflict previews require the user-confirmed resolution plan. Explain conflicts using both commit ancestry and the actual conflicting regions. This first version does not silently extend the same protocol to cherry-pick or rebase.

## 9. Conservative scripts

Scripts may enforce mechanical invariants such as lock creation, snapshot identity, Git identity, unmerged-index rejection, tree sealing, and post-commit tree equality. They must not decide document impact, wording, atomic boundaries, ecosystem, conflict semantics, or user choices. When a script is unavailable or ambiguous, read the files and make the judgment in the Agent; do not replace a missing script with a broad automatic mutation.

## 10. Failure and handback

A failed checkpoint is not a reason to erase user work. Preserve the lock while diagnosing so ownership remains unambiguous. If the user chooses abandonment, run the explicit abort operation, state that no commit was completed, and return Git/index ownership to the main Agent. A successful handback always includes the commit hash, exact frozen title, final tree verification, residual worktree state, limitations, and lock-cleared confirmation.
