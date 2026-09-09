# Agent Repository Governance

Three independent Codex Skills for Agent-oriented repository initialization and checkpoint maintenance:

- `bootstrap-agent-repo`: initializes the Agent-facing repository structure without changing business code.
- `save-checkpoint`: lets the main Agent freeze a staged snapshot and delegate the checkpoint.
- `checkpoint-maintenance`: lets the checkpoint child maintain documentation, commit, verify, and hand back.

This repository is a multi-Skill distribution unit, not a parent Skill and not a Codex Plugin. After installation, the three directories appear as three separate Skills.

## Install all three Skills

Using the built-in Skill installer:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo <owner>/agent-repo-governance \
  --path \
    .agents/skills/bootstrap-agent-repo \
    .agents/skills/save-checkpoint \
    .agents/skills/checkpoint-maintenance
```

Use `--ref <tag-or-branch>` to install a pinned version. The default destination is the user Skill directory (`~/.codex/skills`). To install into a project instead, add:

```bash
--dest /path/to/project/.agents/skills
```

On Windows PowerShell, use the same Python script with the corresponding local path to your `.codex` directory.

## Included package

```text
.agents/skills/
├── bootstrap-agent-repo/
├── save-checkpoint/
└── checkpoint-maintenance/
```

The maintenance philosophy and supporting references remain inside the Skill package. Initialization does not unpack them into a target project's documentation.

## Development

Run the Skill validator for each Skill before publishing:

```bash
python3 <path-to-skill-creator>/scripts/quick_validate.py .agents/skills/bootstrap-agent-repo
python3 <path-to-skill-creator>/scripts/quick_validate.py .agents/skills/save-checkpoint
python3 <path-to-skill-creator>/scripts/quick_validate.py .agents/skills/checkpoint-maintenance
```

Keep the three Skills as peer directories. `save-checkpoint` delegates to the explicitly invoked `$checkpoint-maintenance` Skill; it must not be turned into a parent/child directory relationship.

## Project-specific governance

The Skills can preserve local branch protections and review external source copies
without assuming a framework or directory layout. Bootstrap discovers candidates,
resolves uncertain scope with the user, and writes a tracked
`.agents/repo-governance.json`. Each external entry identifies a relative directory,
optional exclusions, and documentation routes. Multiple independent trees are supported.
Projects without configuration retain the original branch-neutral Git-only behavior.

Checkpoints freeze both the staged Git change and registered external SHA-256 evidence.
The maintenance Agent reviews affected source/docs before accepting the baseline;
sealing requires the reviewed configuration and baseline in the index. Hashing uses
Python's standard library, supports symlinks and executable bits, and works in linked
Git worktrees. `check` and `discover` are read-only unless artifact writing is requested.

See the [policy schema and migration guide](.agents/skills/save-checkpoint/references/repository-policy.md)
and [external review protocol](.agents/skills/checkpoint-maintenance/references/external-code-review.md).
Version-1 checkpoint locks must be completed or deliberately aborted before upgrading.

Run the isolated behavioral tests without writing bytecode into the checkout:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```
