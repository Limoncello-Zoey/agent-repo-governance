---
name: checkpoint-maintenance
description: "Maintain and commit a frozen Git checkpoint after the main Agent delegates it. Use only for the checkpoint child workflow: review the frozen staged diff, update affected semantic documentation and indexes, seal the final tree, commit, verify, and hand back."
---

# Maintain a Frozen Checkpoint

You are the checkpoint child Agent. Read [references/maintenance-philosophy.md](references/maintenance-philosophy.md) before making decisions; it is the authoritative internal guide for document maintenance, routing, atomic changes, and Git ownership. Do not ask the main Agent to restate that guide.

## Non-negotiable handoff contract

The main Agent must have already created a checkpoint lock and supplied:

- repository path;
- `base_head` and current branch;
- frozen Simplified Chinese `frozen_title`;
- lock path;
- user scope, requested Git strategy, and any confirmed decisions.

If the handoff is incomplete, the lock is absent, or the repository is not a Git worktree, stop and report the exact missing condition. Do not repair or guess around a changed snapshot.

## Execution sequence

1. Resolve the repository and checkpoint helper. The current helper is packaged with the peer `save-checkpoint` Skill; locate that installed sibling from the Skill inventory and use its `scripts/checkpoint_guard.py`. Never hardcode a home or project absolute path. Run `verify` before reading the frozen diff.
2. Treat `git diff --cached` as the frozen code snapshot. The main Agent may be editing unstaged engineering files; do not include them.
3. Read the documentation root `INDEX.md`, route through the affected module `INDEX.md`, and inspect only the leaf documents and code evidence relevant to the frozen change. Use targeted `rg` searches for new interfaces, configuration names, events, files, and behavior.
4. Decide which authoritative documents need semantic maintenance. Update only checkpoint-owned docs and indexes; never modify unrelated user documents or source files.
5. Set `last_reviewed_commit_title` to the frozen title only on documents actually updated or semantically revalidated. Do not update markers mechanically.
6. Stage the maintenance documents explicitly. Do not restage later unstaged source work. Review the complete final staged diff and run `git diff --cached --check`.
7. Prepare a detailed Simplified Chinese commit message from the final staged diff. The subject must be exactly the frozen title. If the title is materially wrong, abort and ask the main Agent to refreeze; never silently mutate the title.
8. Run `seal`, create the commit from the prepared message, then run `verify-commit --clear`. Only successful verification with lock removal is a completed checkpoint.
9. Return `checkpoint_done` with commit hash, exact title, code/docs summary, checks run, remaining staged/unstaged changes, limitations, and cleared lock path.

## Git ownership

Until handback, you own the index, checkpoint-owned documents, commit operation, and lock. Do not change branches, rebase, stash, or alter the frozen base. If you cannot continue safely, leave the lock in place while diagnosing; use `abort` only when deliberately abandoning the checkpoint and clearly tell the main Agent that Git ownership is returned.

## Merge execution

For a merge request, rely on the main Agent's read-only preview. If it reported no conflicts, execute the approved merge and verify its result. If it reported conflicts, apply only the user's confirmed resolution plan, inspect all resolved files, and report any deviation. Do not invent a resolution from an ambiguous preview.
