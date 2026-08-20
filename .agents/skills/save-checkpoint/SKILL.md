---
name: save-checkpoint
description: Dispatch a guarded “存一版” checkpoint to a dedicated maintenance subagent. Use when the user asks to save, commit, or checkpoint the current development stage; the main Agent freezes an explicit snapshot and delegates documentation and Git maintenance to $checkpoint-maintenance.
---

# Dispatch a Development Checkpoint

This Skill is the main Agent's short dispatch protocol. It does not contain the documentation-writing or Git-maintenance philosophy. The main Agent should not load that detail speculatively; the delegated Agent must explicitly use the independent `$checkpoint-maintenance` Skill for it.

## Main Agent responsibilities

1. Confirm the user's intended scope, branch, and whether unrelated staged work is included. Do not guess when the scope is ambiguous.
2. Inspect the repository status, staged/unstaged diff, and untracked files without changing Git state.
3. Select one coherent atomic change. “Atomic” means one user-intent slice that can be explained and verified; it does not mean one file or one document.
4. Run the cheapest relevant pre-concurrency checks, then stage only explicit paths or hunks. Do not use `git add .` by default.
5. Draft a concise Simplified Chinese title from the staged diff and freeze it with the repository's checkpoint guard. Resolve the loaded `save-checkpoint` Skill directory rather than assuming a project or home path:

   ```bash
   python3 <save-checkpoint-skill-dir>/scripts/checkpoint_guard.py freeze --repo <repo> --title "<frozen title>"
   ```

   Do not create the child Agent until `snapshot_frozen` succeeds.
6. Create a dedicated checkpoint child Agent and pass it the emitted `base_head`, `branch`, `frozen_title`, `lock_path`, repository path, user intent, and any explicit decisions. Instruct it to use `$checkpoint-maintenance`.
7. Wait for `checkpoint_done`, a clear failure, or a request for user input. Do not resume Git state-changing operations before successful handback.

## Ownership while the child runs

The main Agent may continue ordinary unstaged engineering work after the snapshot is frozen. While the lock exists, it must not run `git add`, `git reset`, `git stash`, `git commit`, `git rebase`, `git checkout`, switch branches, change `HEAD`, or edit documents assigned to the child.

The child owns the index, checkpoint documents, commit, verification, and lock cleanup. If subagents are unavailable, use the same freeze/verify/seal/commit/handback sequence serially and disclose that no parallel development was possible.

## Merge requests

If the user's Git instruction includes `git merge`, the main Agent performs a read-only merge preview first (for example with `git merge-tree` or an equivalent temporary comparison). It must not execute the merge during preview.

Resolve the current `HEAD` and target ref first, then prefer the installed Git's supported `git merge-tree` mode. Capture the predicted tree/conflict sections and inspect the relevant commits/diffs; do not treat a zero exit status alone as an explanation.

- If there is no conflict, pass the target branch and preview result to the checkpoint child for execution.
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
```

The child must return the commit hash, frozen title, verification summary, remaining staged/unstaged changes, limitations, and lock-cleared confirmation before the main Agent reports completion.
