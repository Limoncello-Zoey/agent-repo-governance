# Repository Guidelines

This repository distributes three independent Skills under `.agents/skills/`. Keep each Skill self-contained, validate each `SKILL.md` before publishing, and preserve relative links to its own `references/`, `assets/`, and `scripts/`.

Do not merge the three Skills into a parent Skill. Keep the detailed maintenance philosophy inside `checkpoint-maintenance`; do not copy it into a target project's documentation during installation or bootstrap.

The built-in Skill installer can install all three paths from this repository in one operation. Use tagged releases when consumers need reproducible versions.
