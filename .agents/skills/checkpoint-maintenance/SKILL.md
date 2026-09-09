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
- user scope, requested Git strategy, and any confirmed decisions;
- the emitted `maintenance_paths` list, including an empty list when no initially staged docs are delegated;
- the freeze output’s `external` evidence and `external_artifacts` paths (including disabled status).

If the handoff is incomplete, the lock is absent, or the repository is not a Git worktree, stop and report the exact missing condition. Do not repair or guess around a changed snapshot.

## Branch and authorization gate

Verify the handoff and current branch against the project's configured protected
branches before touching the index, before sealing and immediately before committing.
Never repair a protected-branch handoff by switching branches; return ownership for
normalization and refreezing. A valid scoped checkpoint handoff authorizes routine
maintenance, local commit, verification and cleanup without repetitive confirmation;
it does not authorize publication, unrelated changes or unrequested history operations.

## Execution sequence

1. Resolve the repository and checkpoint helper. The current helper is packaged with the peer `save-checkpoint` Skill; locate that installed sibling from the Skill inventory and use its `scripts/checkpoint_guard.py`. Never hardcode a home or project absolute path. Run `verify` before reading the frozen diff.
2. Initial staged documents listed in `maintenance_paths` are checkpoint-owned and may be updated. Other initially staged files remain immutable; if additional initially staged docs need edits, stop and request refreezing with explicit ownership. Read their original blobs from the lock’s `initial_staged` records when needed. Treat `git diff --cached` and the locked external report as the frozen evidence. The main Agent may be editing unstaged engineering files; do not include them. When external checks are enabled or the registry scope changes, read [references/external-code-review.md](references/external-code-review.md), independently verify the candidate, review changes and maintain routed docs before accepting a baseline.
3. Read the documentation root `INDEX.md`, route through the affected module `INDEX.md`, and inspect only the leaf documents and code evidence relevant to the frozen change. Use targeted `rg` searches for new interfaces, configuration names, events, files, and behavior.
4. Decide which authoritative documents need semantic maintenance. Update only checkpoint-owned docs and indexes; never modify unrelated user documents or source files.
5. Set `last_reviewed_commit_title` to the frozen title only on documents actually updated or semantically revalidated. Do not update markers mechanically.
6. Accept the external baseline only after the required review, then stage it and its configuration explicitly when changed. Stage the maintenance documents explicitly. Do not restage later unstaged source work. Review the complete final staged diff and run `git diff --cached --check`.
7. Prepare a detailed Simplified Chinese commit message from the final staged diff. The subject must be exactly the frozen title. If the title is materially wrong, abort and ask the main Agent to refreeze; never silently mutate the title.
8. Recheck the branch, run `seal`, recheck immediately before creating the commit, then run `verify-commit --clear`. Seal verifies the original frozen index entries except explicitly delegated maintenance documents and requires staged governance configuration/baseline bytes to match reviewed evidence; verification also checks the commit subject. Only successful verification with lock removal is a completed checkpoint.
9. Return `checkpoint_done` with commit hash, exact title, code/docs summary, external-source review and coverage changes, checks run, remaining staged/unstaged changes, limitations, and cleared lock path.

## Git ownership

Until handback, you own the index, checkpoint-owned documents, commit operation, and lock. Do not change branches, rebase, stash, or alter the frozen base. If you cannot continue safely, leave the lock in place while diagnosing; use `abort` only when deliberately abandoning the checkpoint and clearly tell the main Agent that Git ownership is returned.

## Merge execution

For a merge request, rely on the main Agent's read-only preview. Complete or deliberately abort the frozen checkpoint and hand back Git ownership before an approved merge; a two-parent merge cannot pass the helper's sole-parent checkpoint verification. Execute separately and refreeze any subsequent checkpoint at the resulting HEAD. If it reported conflicts, apply only the user's confirmed resolution plan, inspect all resolved files, and report any deviation. Do not invent a resolution from an ambiguous preview.
