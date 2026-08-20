#!/usr/bin/env python3
"""Produce a read-only inventory for Agent-oriented repository bootstrapping."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "target",
    "coverage",
    "__pycache__",
}

MANIFESTS = (
    "package.json",
    "pnpm-workspace.yaml",
    "pyproject.toml",
    "requirements.txt",
    "uv.lock",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "Gemfile",
    "composer.json",
    "Makefile",
    "justfile",
    "Taskfile.yml",
    "docker-compose.yml",
    "compose.yaml",
)

COMMON_DIR_GROUPS = {
    "source": ("src", "app", "lib", "packages", "services", "cmd", "internal"),
    "tests": ("tests", "test", "spec", "e2e", "integration"),
    "assets": ("assets", "public", "static", "resources", "fixtures"),
    "documentation": ("docs", "documentation", "doc"),
}
DOCUMENTATION_DIR_NAMES = frozenset(
    name.casefold() for name in COMMON_DIR_GROUPS["documentation"]
)


def run(command: list[str], cwd: Path) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        return 127, ""
    return result.returncode, result.stdout.strip()


def resolve_root(candidate: Path) -> tuple[Path, bool]:
    candidate = candidate.resolve()
    code, output = run(["git", "rev-parse", "--show-toplevel"], candidate)
    if code == 0 and output:
        return Path(output).resolve(), True
    return candidate, False


def walk_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current, directories, names in os.walk(root):
        directories[:] = [
            name
            for name in directories
            if name not in SKIP_DIRS and not name.startswith(".cache")
        ]
        base = Path(current)
        for name in names:
            path = base / name
            if path.is_symlink():
                continue
            files.append(path)
    return files


def relative_strings(root: Path, paths: list[Path]) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in paths)


def discover_documentation_roots(root: Path) -> list[Path]:
    """Find supported root documentation directories without normalizing case."""
    try:
        children = root.iterdir()
    except OSError:
        return []
    return sorted(
        (
            path
            for path in children
            if path.is_dir() and path.name.casefold() in DOCUMENTATION_DIR_NAMES
        ),
        key=lambda path: (path.name.casefold(), path.name),
    )


def is_within(path: Path, roots: list[Path]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def package_scripts(root: Path) -> dict[str, str]:
    path = root / "package.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return {}
    return {
        str(name): str(command)
        for name, command in scripts.items()
        if isinstance(name, str) and isinstance(command, str)
    }


def make_targets(root: Path) -> list[str]:
    path = root / "Makefile"
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    targets: set[str] = set()
    for line in text.splitlines():
        if line.startswith((" ", "\t", "#")) or "=" in line.split(":", 1)[0]:
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*:(?![=])", line)
        if match and "%" not in match.group(1):
            targets.add(match.group(1))
    return sorted(targets)


def git_info(root: Path, is_git: bool) -> dict[str, Any]:
    if not is_git:
        return {"is_repository": False}
    _, branch = run(["git", "branch", "--show-current"], root)
    _, status = run(["git", "status", "--short"], root)
    _, log = run(["git", "log", "-5", "--pretty=format:%h\t%s"], root)
    return {
        "is_repository": True,
        "branch": branch or "(detached or unborn)",
        "status": status.splitlines() if status else [],
        "recent_commits": log.splitlines() if log else [],
    }


def documentation_tree(root: Path, documentation_roots: list[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for docs_root in documentation_roots:
        for current, directories, names in os.walk(docs_root):
            directories[:] = [name for name in directories if name not in SKIP_DIRS]
            current_path = Path(current)
            markdown_names = sorted(
                name for name in names if Path(name).suffix.lower() in {".md", ".mdx"}
            )
            entries.append(
                {
                    "path": current_path.relative_to(root).as_posix(),
                    "has_index": any(name.lower() in {"index.md", "index.mdx"} for name in names),
                    "child_directories": sorted(directories),
                    "markdown_files": markdown_names,
                }
            )
    return entries


def build_inventory(root: Path, is_git: bool) -> dict[str, Any]:
    files = walk_files(root)
    documentation_roots = discover_documentation_roots(root)
    markdown = [path for path in files if path.suffix.lower() in {".md", ".mdx"}]
    docs = [
        path
        for path in markdown
        if is_within(path, documentation_roots)
        or path.name.lower() in {"readme.md", "contributing.md", "architecture.md"}
    ]
    agent_files = [
        path
        for path in files
        if path.name in {"AGENTS.md", "AGENTS.override.md"}
        or ".agents" in path.relative_to(root).parts
        or ".codex" in path.relative_to(root).parts
        or ".agent-state" in path.relative_to(root).parts
    ]
    extension_counts = Counter(
        path.suffix.lower() or "[no extension]" for path in files
    )

    return {
        "root": str(root),
        "git": git_info(root, is_git),
        "manifests": [name for name in MANIFESTS if (root / name).is_file()],
        "common_directories": {
            group: (
                [path.name for path in documentation_roots]
                if group == "documentation"
                else [name for name in names if (root / name).is_dir()]
            )
            for group, names in COMMON_DIR_GROUPS.items()
        },
        "package_scripts": package_scripts(root),
        "make_targets": make_targets(root),
        "documentation_files": relative_strings(root, docs),
        "documentation_tree": documentation_tree(root, documentation_roots),
        "agent_environment_files": relative_strings(root, agent_files),
        "file_extensions": dict(extension_counts.most_common(15)),
        "file_count": len(files),
    }


def print_markdown(data: dict[str, Any]) -> None:
    print("# Repository inventory")
    print(f"\n- Root: `{data['root']}`")
    print(f"- Files scanned: {data['file_count']}")

    git = data["git"]
    print("\n## Git")
    print(f"\n- Repository: {'yes' if git.get('is_repository') else 'no'}")
    if git.get("is_repository"):
        print(f"- Branch: `{git.get('branch')}`")
        status = git.get("status", [])
        print(f"- Working tree entries: {len(status)}")
        if status:
            for entry in status[:40]:
                print(f"  - `{entry}`")
            if len(status) > 40:
                print(f"  - … {len(status) - 40} more")
        commits = git.get("recent_commits", [])
        if commits:
            print("\nRecent commits:")
            for entry in commits:
                print(f"- `{entry}`")

    print("\n## Project evidence")
    manifests = data["manifests"]
    print("\nManifests and task runners:")
    if manifests:
        for item in manifests:
            print(f"- `{item}`")
    else:
        print("- None detected at the repository root")

    for group, directories in data["common_directories"].items():
        rendered = ", ".join(f"`{item}/`" for item in directories) or "none detected"
        print(f"- {group}: {rendered}")

    if data["package_scripts"]:
        print("\nPackage scripts:")
        for name, command in sorted(data["package_scripts"].items()):
            print(f"- `npm run {name}` → `{command}`")

    if data["make_targets"]:
        print("\nMake targets:")
        for target in data["make_targets"]:
            print(f"- `make {target}`")

    print("\n## Documentation")
    if data["documentation_files"]:
        for item in data["documentation_files"]:
            print(f"- `{item}`")
    else:
        print("- No documentation entry points detected")

    if data["documentation_tree"]:
        print("\nDocumentation directories:")
        for entry in data["documentation_tree"]:
            index_state = "INDEX present" if entry["has_index"] else "INDEX missing"
            children = ", ".join(entry["child_directories"]) or "none"
            markdown_count = len(entry["markdown_files"])
            print(
                f"- `{entry['path']}/`: {index_state}; "
                f"child directories: {children}; direct Markdown files: {markdown_count}"
            )

    print("\n## Existing Agent environment")
    if data["agent_environment_files"]:
        for item in data["agent_environment_files"]:
            print(f"- `{item}`")
    else:
        print("- None detected")

    print("\n## Dominant file extensions")
    for extension, count in data["file_extensions"].items():
        print(f"- `{extension}`: {count}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", nargs="?", default=".")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()

    candidate = Path(args.repository)
    if not candidate.is_dir():
        print(f"error: repository directory does not exist: {candidate}", file=sys.stderr)
        return 2

    root, is_git = resolve_root(candidate)
    data = build_inventory(root, is_git)
    if args.format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print_markdown(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
