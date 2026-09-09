# Repository policy and external source evidence

Read this when a project uses protected branches or maintains external source copies.
The optional, tracked `.agents/repo-governance.json` is the helper configuration.
Existing project instructions and explicit user decisions remain authoritative; reconcile
conflicts before freezing. An absent configuration preserves branch-neutral Git-only
behavior. Do not infer a universal `main/dev` policy from this Skill.

## Configuration

```json
{
  "version": 1,
  "branches": {
    "protected": ["main", "dev"],
    "base": "dev",
    "task_prefix": "feature/"
  },
  "external_code": [
    {
      "id": "device-sdk",
      "path": "third_party/device-sdk",
      "exclude": ["build", "cache"],
      "docs": ["docs/integrations/device-sdk.md"]
    },
    {
      "id": "legacy-library",
      "path": "external/legacy-library",
      "docs": ["docs/integrations/legacy-library.md"]
    }
  ]
}
```

Both `branches` and `external_code` are optional. `external_code: []` explicitly
registers no external trees. Branch names are exact names, not patterns. For a single
protected main branch use `protected: ["main"]`, `base: "main"`; retain the actual
project branch model. If no branches are protected, omit `branches` or use an empty
`protected` list. New tasks use `task_prefix` plus local `YYYYMMDD-HHMMSS`; established
non-protected branches do not need to match that naming convention.

Each external entry has a unique stable `id`, a repository-relative directory `path`,
optional `exclude` paths relative to that directory, and optional `docs` paths relative
to the repository. Paths use canonical POSIX notation, without `..`, absolute paths,
or symlink ancestors. Roots cannot overlap or contain governance metadata. Review docs must live outside
the registered roots so documentation edits cannot change the frozen source evidence. Exclusions
are exact paths and their descendants, not globs. Document the reason for exclusions
in the routed project documentation; never use exclusions merely to hide a diff.
The helper rejects unknown fields to avoid silently ignoring misspelled policy.

Choose source copies that the project actually maintains or relies on and that need
review beyond normal Git diffs. Git-ignored and untracked trees are common cases;
tracked external copies can also be registered deliberately. Their staged bytes and
modes must match the live fingerprint at freeze/seal; commit verification checks the
committed blobs too. Partial staging with different live external content fails: resolve
the intended scope and refreeze, never implicitly stage later source work. Git submodules
use their pinned-repository review workflow; gitlinks in registered source scope are
rejected rather than pretending a copied-tree fingerprint verifies the submodule pin. Package caches, generated
builds, secrets, datasets and user-home directories are not implicit candidates.

## Initialization and changes to scope

Run the read-only candidate finder:

```bash
python3 <save-checkpoint-dir>/scripts/external_snapshot.py discover --repo <repo>
```

It only recognizes conventional directory names within a bounded depth, skips common
build/dependency caches, and never registers anything. Read manifests, dependency
locks, `.gitmodules`, ignore rules, build references and project docs to confirm the
actual purpose. Do not recurse into candidate trees merely for discovery. Register
well-evidenced external source roots within the requested bootstrap scope. If ownership,
large scan scope or exclusions are uncertain, ask one focused question listing the
candidates and their evidence; continue independent initialization work meanwhile.
Allow manually supplied arbitrary relative directories. No detected candidates does
not prove no external code exists; report the discovery limits.

Before the first baseline, review the selected source trees and maintain the relevant
project documentation, including limitations of static review. Then run:

```bash
python3 <save-checkpoint-dir>/scripts/external_snapshot.py snapshot --repo <repo> --reviewed
```

This creates `.agents/external-code.snapshot.json` and refuses to overwrite an existing
baseline. The flag records the caller's attestation, not automated proof of review.
Missing baseline with registered roots is a hard error, never an empty snapshot.
Bootstrap leaves configuration, baseline and docs uncommitted. If the review cannot be
completed within scope, report the pending baseline explicitly; do not claim readiness.

Adding/removing roots, changing IDs/paths or exclusions is a review-scope change.
Review both the tracked config diff and the old baseline. Removing an entire root or
registering an empty list requires explaining the loss of coverage and updating routes;
do not do it to bypass a missing directory or hash failure. For remaining enabled roots,
the normal checkpoint report captures scope changes and accepts the new baseline after
review. When disabling all roots, deliberately retire the old baseline and document why.

## Hashing and evidence contract

`check` is read-only by default; `--write-artifacts` explicitly writes the candidate
and report in the actual per-worktree Git directory. `freeze` writes these artifacts
after creating its lock. Never hardcode `<repo>/.git/`: linked worktrees use a `.git` file.
Exit codes for external checks: `0` unchanged/disabled, `3` changed, `4` error.

SHA-256 uses Python's streaming standard-library implementation on all platforms; no
RHash installation or ROS package parser is required. The JSON baseline records root
IDs, paths, exclusions, file hashes, executable bits and symlink target hashes. Symlink
targets are never followed, including directory links. VCS metadata is always excluded.
Special files fail instead of being read. Empty directories are not recorded. Renames
are reported as deletion plus addition. A manifest hash is not a source backup,
provenance statement, license audit or reproducible dependency pin.

The lock stores the config-byte digest, original baseline digest, candidate digest and
original change report. Repeated checks must match the frozen config and candidate.
An accepted baseline may match the candidate; any other baseline drift stops the task.
A live filesystem is not an atomic snapshot: detected in-read changes fail, and repeated
boundary checks detect stable drift. Pause writers if a consistent scan cannot be obtained.

## Branch normalization

```bash
python3 <save-checkpoint-dir>/scripts/checkpoint_guard.py branch-preflight \
  --repo <repo> --target <prefix><local-YYYYMMDD-HHMMSS>
```

Omit `--target` on an established non-protected branch. `action: stop` also exits `4`.
The helper never switches branches, fetches or pulls. It reports the configured base
and divergence from its locally known upstream, not guaranteed remote freshness.

On a protected branch, switch to the configured existing base first and create a task
branch there. Dirty state can move only when the current HEAD equals that base; an
existing target must equal the base too. A dirty base may create a task ref without
stash/restaging. Ordinary Git must reject overwrites. Stop on conflicts, unfinished Git
operations, detached/unborn HEAD, missing base, different target history, another
worktree owning the base/target, or an existing checkpoint lock. Never use stash,
reset, clean, forced switch or a temporary commit to silently transplant user work.
Execute only the ordinary transitions described by the preflight, then recheck status.
The child never normalizes branches after ownership has been frozen.

## Compatibility

Checkpoint locks now use schema version 2; finish or deliberately abort old checkpoints
before upgrading. There is no automatic lock migration. Existing repositories without
configuration retain Git-only operation. For a legacy single-vendor manifest, do not
rename the old file into the JSON baseline: reconcile its changes and complete an
explicit initial review before creating the new baseline. Keep the previous evidence
until that review is complete. No ROS-specific catalog generator or mandatory domain
Skill is installed; route to the project's actual ecosystem documentation and tools.

## Staged documentation ownership

At freeze, repeated `--maintenance-path <doc>` arguments declare the specific staged
review documents the child may change. This supports first-bootstrap checkpoints where
staged docs still have null review markers. The lock retains their initial blob IDs for
review, but `verify`/`seal` permit their maintenance updates. Other initial staged blobs
remain immutable. Governance config, baseline and registered external source paths cannot
use this exception. Selecting real documentation is the main Agent's responsibility;
the script does not infer document semantics from filenames. Hand back and refreeze if
a further initially staged document needs ownership; never edit the lock to expand scope.
