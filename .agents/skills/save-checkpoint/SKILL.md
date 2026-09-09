---
name: save-checkpoint
description: Dispatch a guarded “存一版” checkpoint to a dedicated maintenance subagent. Use when the user asks to save, commit, or checkpoint the current development stage; the main Agent freezes an explicit snapshot and delegates documentation and Git maintenance to $checkpoint-maintenance.
---

# Dispatch a Development Checkpoint

This Skill is the main Agent's short dispatch protocol. It does not contain the documentation-writing or Git-maintenance philosophy. The main Agent should not load that detail speculatively; the delegated Agent must explicitly use the independent `$checkpoint-maintenance` Skill for it.

## Project policy and ordinary authorization

Read [references/repository-policy.md](references/repository-policy.md) when the project
has protected branches, registered external source directories, or needs those policies
established. Use the tracked `.agents/repo-governance.json`; do not hardcode branch names,
source paths, an ecosystem, or hash-tool installations. Preserve Git-only operation when
no configuration exists, while still obeying project instructions.

Before staging or freezing, inspect branch, HEAD, index/worktree/untracked state and
unfinished Git operations. Run `checkpoint_guard.py branch-preflight --repo <repo>`;
provide `--target <configured-prefix><local-YYYYMMDD-HHMMSS>` when normalization is
needed. Execute only its ordinary allowed branch transitions and recheck status.
Never freeze on a configured protected branch. Do not silently fetch/pull or transplant
dirty work across different bases. Existing non-protected branches remain valid.

A checkpoint request authorizes ordinary inspection, explicit staging, freezing,
delegation, documentation maintenance, local commit, verification and lock cleanup
within the stated scope. Do not request repetitive confirmation when intent is clear.
This does not add permission to push, publish, merge, or change unrelated files. Stop
for material scope ambiguity, conflicts, changed frozen evidence or missing credentials.

## Main Agent responsibilities

1. Infer scope from the request and inspect unrelated staged work. Proceed when scope is clear; ask only if ambiguity changes what will be committed.
2. Inspect the repository status, staged/unstaged diff, and untracked files without changing Git state.
3. Select one coherent atomic change. “Atomic” means one user-intent slice that can be explained and verified; it does not mean one file or one document.
4. If external roots are registered, run `external_snapshot.py check --repo <repo>` from this Skill. Read its report; a missing baseline is a hard error. Do not accept a changed baseline in the main Agent. Include external changes in the intended review scope and title. Then run the cheapest relevant checks and stage only explicit paths or hunks, not `git add .`.
5. Draft a concise Simplified Chinese title from the staged diff and external report and freeze it with the repository's checkpoint guard. Resolve the loaded `save-checkpoint` Skill directory rather than assuming a project or home path:

   ```bash
   python3 <save-checkpoint-skill-dir>/scripts/checkpoint_guard.py freeze --repo <repo> --title "<frozen title>"
   ```

   Add repeatable `--maintenance-path <doc>` arguments for already-staged documentation the child will own and may need to update (for example first-bootstrap review markers). Inspect those paths explicitly; never delegate source files or governance evidence as documents. Other initial staged blobs stay immutable.

   Do not create the child Agent until `snapshot_frozen` succeeds. An empty ordinary staged diff is allowed only when registered external sources changed. Freeze pins the configuration and both evidence surfaces; do not edit registered external trees, their baseline or configuration until handback.
6. Create a dedicated checkpoint child Agent and pass it the emitted `base_head`, `branch`, `frozen_title`, `lock_path`, repository path, user intent, explicit decisions, and emitted `external` evidence plus `external_artifacts` paths. Instruct it to use `$checkpoint-maintenance`.
7. Wait for `checkpoint_done`, a clear failure, or a request for user input. Do not resume Git state-changing operations before successful handback.

## Ownership while the child runs

The main Agent may continue ordinary unstaged engineering work after the snapshot is frozen. While the lock exists, it must not run `git add`, `git reset`, `git stash`, `git commit`, `git rebase`, `git checkout`, switch branches, change `HEAD`, or edit documents assigned to the child.

The child owns the index, checkpoint documents, commit, verification, and lock cleanup. If subagents are unavailable, use the same freeze/verify/seal/commit/handback sequence serially and disclose that no parallel development was possible.

## Merge requests

If the user's Git instruction includes `git merge`, the main Agent performs a read-only merge preview first (for example with `git merge-tree` or an equivalent temporary comparison). It must not execute the merge during preview.

Resolve the current `HEAD` and target ref first, then prefer the installed Git's supported `git merge-tree` mode. Capture the predicted tree/conflict sections and inspect the relevant commits/diffs; do not treat a zero exit status alone as an explanation.

- If there is no conflict, pass the target branch and preview result to the checkpoint child. A merge is a separate authorized history operation: complete or deliberately abort any active checkpoint before executing it, then refreeze subsequent work at the resulting HEAD.
- If there is a conflict, show the conflicting files/regions, explain both sides using the commit tree, and propose choices. Only after the user confirms a resolution may the child execute the merge and resolve it.

This first version does not automatically generalize the preview protocol to rebase or cherry-pick.

## Handoff format

Use a compact handoff such as:

```text
Use $checkpoint-maintenance in <repo>.
event: snapshot_frozen
base_head: <sha>
branch: <branch>
frozen_title: <title>
lock_path: <path>
user_intent: <scope and requested strategy>
decisions: <confirmed choices or “agent may decide”>
external: <freeze output, including enabled/config/candidate/baseline digests and original report>
external_artifacts: <freeze output; empty when external checks are disabled>
maintenance_paths: <explicit checkpoint-owned document paths from freeze>
```

The child must return the commit hash, frozen title, verification summary, remaining staged/unstaged changes, limitations, and lock-cleared confirmation before the main Agent reports completion.
