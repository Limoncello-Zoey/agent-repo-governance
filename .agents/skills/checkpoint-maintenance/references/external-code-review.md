# Review registered external source changes

Use this for registered external directories or changes to their review scope. Resolve
`external_snapshot.py` from the sibling `save-checkpoint` Skill; its
`references/repository-policy.md` defines the registry, hashing and branch contract.
No specific ecosystem or package layout is required.

## Evidence and ownership

Run checkpoint `verify` first, then the read-only `external_snapshot.py check` yourself.
Require the frozen candidate and config digests. Review the original report stored in
the checkpoint lock, not just a mutable report file: after acceptance the live report
may say unchanged. Missing baseline, missing registered directories, scan errors or
changed evidence stop the checkpoint. Keep the lock until deliberate abort/handback.

The main Agent must not edit registered external trees, their config or baseline during
your review. Candidate/report files belong in the actual worktree Git directory and
are never staged. The baseline and registry are tracked project evidence, not backups,
license records or proof of upstream provenance.

## Review and documentation

Review every added/modified file in each affected root and the necessary surviving
callers, manifests, entry points, configuration, interfaces and build context. For
binary files establish type, role and references without rendering them as text.
For deletions, use preserved old source when available; otherwise inspect surviving
references and state that deleted content was unavailable. Do not infer deletion impact
solely from files still present. Moves appear as additions and deletions.

Resolve `docs` routes in the configured root entries and the authoritative project
index. If routes are absent, select or create an appropriate semantic leaf document
under the existing docs structure. Review config changes against the staged diff and
old baseline, including removed roots and broadened exclusions; explain any loss of
coverage. A missing directory is not authorization to remove it from the registry.

Maintain verified purpose, inputs/outputs, public interfaces, defaults, dependencies,
entry points, lifecycle and compatibility constraints where affected. Use existing
language/framework/hardware Skills when actually needed and available; no ROS Skill
is mandatory. Static inspection is not build/runtime/hardware validation. Preserve
provenance and reproducibility limitations. Update indexes only if routes or semantics
change, and review-title markers only for documents actually maintained/revalidated.
Use an existing project catalog tool when appropriate; do not generate a universal
package catalog or mechanically rewrite every external document.

## Accept and stage

After review, rerun `check` and require the same candidate digest, then:

```bash
python3 <save-checkpoint-dir>/scripts/external_snapshot.py accept \
  --repo <repo> --expected-sha256 <frozen-candidate-sha256>
```

Acceptance requires the active version-2 checkpoint lock, unchanged HEAD/branch/config,
and a live tree matching the frozen candidate. It writes only the tracked baseline.
Skip acceptance when the baseline already matches and no external change needs review.
Stage `.agents/external-code.snapshot.json`, changed `.agents/repo-governance.json`,
and reviewed documents by explicit paths. Never stage external directories merely
because they were fingerprinted. Do not restage unrelated engineering work.

Run `verify`, then `seal`; a missing/unstaged accepted baseline fails sealing. Commit
with the exact frozen subject, run `verify-commit --clear`, and report external roots
reviewed, coverage changes, validation limits and remaining user changes.
