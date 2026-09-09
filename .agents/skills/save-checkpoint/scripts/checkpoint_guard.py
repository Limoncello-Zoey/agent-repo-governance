#!/usr/bin/env python3
"""Guard a staged Git checkpoint while unstaged development continues."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, NoReturn


LOCK_NAME = "agent-checkpoint.lock"
SCHEMA_VERSION = 2

sys.dont_write_bytecode = True
import external_snapshot as external


class GuardError(Exception):
    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


def fail(message: str, code: int = 1) -> NoReturn:
    raise GuardError(message, code)


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    command = ["git", "-C", os.fspath(repo), *args]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError as exc:
        fail(f"无法执行 Git：{exc}", 5)
    if check and result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        fail(f"Git 命令失败（{' '.join(args)}）：{detail or '无错误信息'}", 5)
    return result


def text_git(repo: Path, *args: str, check: bool = True) -> str:
    return run_git(repo, *args, check=check).stdout.decode("utf-8", "surrogateescape").strip()


def resolve_repo(value: str) -> tuple[Path, Path, Path]:
    repo = Path(value).expanduser().resolve()
    if not repo.exists():
        fail(f"仓库路径不存在：{repo}", 2)
    top_result = run_git(repo, "rev-parse", "--show-toplevel", check=False)
    if top_result.returncode:
        detail = top_result.stderr.decode("utf-8", "replace").strip()
        fail(f"不是 Git 工作树：{repo}（{detail or '无法解析仓库'}）", 2)
    top = Path(top_result.stdout.decode("utf-8", "surrogateescape").strip()).resolve()
    git_dir = Path(text_git(repo, "rev-parse", "--absolute-git-dir")).resolve()
    return top, git_dir, git_dir / LOCK_NAME


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def read_lock(lock_path: Path) -> dict[str, Any]:
    try:
        with lock_path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except FileNotFoundError:
        fail(f"检查点锁不存在：{lock_path}", 3)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"无法读取检查点锁 {lock_path}：{exc}", 3)
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        fail(f"检查点锁格式或版本无效：{lock_path}", 3)
    return data


def write_new_lock(lock_path: Path, data: dict[str, Any]) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{LOCK_NAME}.", dir=lock_path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temp_path, lock_path)
        except FileExistsError:
            fail(f"已有检查点锁，拒绝覆盖：{lock_path}", 3)
        except OSError as exc:
            fail(f"无法原子创建检查点锁 {lock_path}：{exc}", 3)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def replace_lock(lock_path: Path, data: dict[str, Any]) -> None:
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{LOCK_NAME}.", dir=lock_path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, lock_path)
    except OSError as exc:
        fail(f"无法更新检查点锁 {lock_path}：{exc}", 3)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def current_head(repo: Path) -> str:
    result = run_git(repo, "rev-parse", "--verify", "HEAD", check=False)
    if result.returncode:
        fail("仓库尚无 HEAD 提交，无法冻结 base HEAD", 4)
    return result.stdout.decode("ascii").strip()


def current_branch(repo: Path) -> str:
    result = run_git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if result.returncode:
        fail("当前处于 detached HEAD，无法冻结分支", 4)
    return result.stdout.decode("utf-8", "surrogateescape").strip()


def staged_paths(repo: Path) -> list[str]:
    raw = run_git(
        repo,
        "diff",
        "--cached",
        "--name-only",
        "-z",
        "--diff-filter=ACDMRTUXB",
    ).stdout
    return [item.decode("utf-8", "surrogateescape") for item in raw.split(b"\0") if item]


def index_entry(repo: Path, path: str) -> dict[str, Any]:
    raw = run_git(repo, "ls-files", "--stage", "-z", "--", path).stdout
    records = [record for record in raw.split(b"\0") if record]
    if not records:
        return {"path": path, "mode": None, "blob": None}
    if len(records) != 1:
        fail(f"暂存路径存在未合并 index 项：{path}", 4)
    metadata, separator, encoded_path = records[0].partition(b"\t")
    fields = metadata.split()
    decoded_path = encoded_path.decode("utf-8", "surrogateescape")
    if not separator or len(fields) != 3 or fields[2] != b"0" or decoded_path != path:
        fail(f"无法解析暂存路径的 index 项：{path}", 4)
    return {
        "path": path,
        "mode": fields[0].decode("ascii"),
        "blob": fields[1].decode("ascii"),
    }


def initial_entries(repo: Path) -> list[dict[str, Any]]:
    ensure_no_unmerged(repo)
    paths = staged_paths(repo)
    return [index_entry(repo, path) for path in paths]


def ensure_no_unmerged(repo: Path) -> None:
    if run_git(repo, "ls-files", "--unmerged", "-z").stdout:
        fail("index 中存在未合并项，无法继续检查点", 4)


def policy(repo: Path) -> dict:
    return external.load_config(repo)[0].get("branches", {})


def ensure_checkpoint_branch(repo: Path) -> str:
    branch = current_branch(repo)
    if branch in policy(repo).get("protected", []):
        fail(f"Protected branch {branch!r}; normalize to a task branch before freezing", 4)
    return branch


def ref_commit(repo: Path, ref: str) -> str | None:
    result = run_git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False)
    return result.stdout.decode().strip() if not result.returncode else None


def in_progress(repo: Path) -> list[str]:
    _, directory, _ = resolve_repo(str(repo))
    markers = ["MERGE_HEAD", "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD",
               "REVERT_HEAD", "BISECT_START", "sequencer"]
    return [name for name in markers if (directory / name).exists()]


def worktree_for(repo: Path, branch: str) -> str | None:
    current = None
    for line in text_git(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            current = line[9:]
        elif line == "branch refs/heads/" + branch:
            return current
    return None


def command_branch_preflight(args: argparse.Namespace) -> None:
    repo, _, lock_path = resolve_repo(args.repo)
    rules = policy(repo)
    branch = text_git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    head = ref_commit(repo, "HEAD")
    base_name = rules.get("base")
    base = ref_commit(repo, "refs/heads/" + base_name) if base_name else None
    target = args.target
    dirty = bool(run_git(repo, "status", "--porcelain=v2", "-z").stdout)
    unmerged = bool(run_git(repo, "ls-files", "--unmerged", "-z").stdout)
    operations = in_progress(repo)
    action, reason = "stop", "No safe branch transition established"
    target_head = ref_commit(repo, "refs/heads/" + target) if target else None
    upstream = text_git(repo, "rev-parse", "--symbolic-full-name", base_name + "@{upstream}", check=False) if base else None
    divergence = text_git(repo, "rev-list", "--left-right", "--count", base_name + "..." + upstream).split() if upstream else None
    if lock_path.exists():
        reason = "A checkpoint already owns Git state"
    elif operations or unmerged or not head or not branch:
        reason = "Unfinished Git operation, conflict, detached or unborn HEAD"
    elif branch not in rules.get("protected", []):
        action, reason = "continue_current_branch", "Existing non-protected branch remains valid"
    elif not base:
        reason = "Protected branch requires an existing configured local base"
    elif not target:
        reason = "Provide a task target using the configured prefix and local YYYYMMDD-HHMMSS"
    elif target in rules.get("protected", []):
        reason = "Target is protected"
    elif run_git(repo, "check-ref-format", "--branch", target, check=False).returncode:
        reason = "Invalid target branch"
    elif worktree_for(repo, target) not in (None, str(repo)) or worktree_for(repo, base_name) not in (None, str(repo)):
        reason = "Base or target is checked out in another worktree"
    elif target_head is not None and target_head != base:
        reason = "Existing target differs from configured base"
    elif target_head is None and not re.fullmatch(re.escape(rules.get("task_prefix", "feature/")) + r"[0-9]{8}-[0-9]{6}", target):
        reason = "New target must use configured prefix and YYYYMMDD-HHMMSS"
    elif dirty and head != base:
        reason = "Dirty protected branch differs from configured base"
    elif branch == base_name:
        action = "switch_existing_at_base" if target_head else "create_from_base_carry_state"
        reason = "HEAD stays at base; preserve index, worktree and untracked files"
    else:
        action = "switch_base_then_existing" if target_head else "switch_base_then_create"
        reason = "Switch to configured base first, then task branch; ordinary Git must reject overwrites"
    emit({"event": "branch_preflight", "action": action, "reason": reason,
          "branch": branch, "head": head, "base_branch": base_name, "base_head": base,
          "target": target, "target_head": target_head, "dirty": dirty, "unmerged": unmerged,
          "in_progress": operations, "upstream": upstream,
          "base_vs_upstream": {"ahead": int(divergence[0]), "behind": int(divergence[1])} if divergence else None})
    if action == "stop":
        fail(reason, 4)


def validate_external(repo: Path, data: dict, tree: str | None = None) -> None:
    current, candidate = external.evidence(repo)
    frozen = data.get("external")
    if not isinstance(frozen, dict):
        fail("Lock lacks external-source evidence; refreeze using this helper version", 4)
    if current.get("config_sha256") != frozen.get("config_sha256") or current.get("enabled") != frozen.get("enabled"):
        fail("Governance configuration changed after freeze", 4)
    if current.get("enabled"):
        if current["candidate_sha256"] != frozen.get("candidate_sha256"):
            fail("External source changed after freeze", 4)
        if current["baseline_sha256"] not in {frozen.get("baseline_sha256"), frozen.get("candidate_sha256")}:
            fail("External baseline changed outside the accepted snapshot", 4)
        external.verify_tracked(repo, json.loads(candidate), tree)


def verify_governance_tree(repo: Path, data: dict, tree: str) -> None:
    frozen = data["external"]
    paths = {external.CONFIG: frozen.get("config_sha256")}
    if frozen.get("enabled"):
        paths[external.BASELINE] = frozen["candidate_sha256"]
    for path, expected in paths.items():
        result = run_git(repo, "show", ("" if tree == ":" else tree) + ":" + path, check=False)
        actual = external.digest(result.stdout) if not result.returncode else None
        if actual != expected:
            fail(f"{path} in {tree} does not match reviewed governance evidence", 4)


def validate_identity(repo: Path, data: dict[str, Any]) -> None:
    expected_head = data.get("base_head")
    expected_branch = data.get("branch")
    head = current_head(repo)
    branch = ensure_checkpoint_branch(repo)
    if head != expected_head:
        fail(f"HEAD 已变化：期望 {expected_head}，实际 {head}", 4)
    if branch != expected_branch:
        fail(f"分支已变化：期望 {expected_branch!r}，实际 {branch!r}", 4)


def verify_snapshot(repo: Path, data: dict[str, Any]) -> None:
    validate_identity(repo, data)
    validate_external(repo, data)
    entries = data.get("initial_staged")
    if not isinstance(entries, list) or (not entries and not data["external"].get("changed")):
        fail("检查点锁缺少初始暂存内容", 3)
    maintenance = data.get("maintenance_paths", [])
    if not isinstance(maintenance, list) or any(not isinstance(p, str) for p in maintenance):
        fail("Invalid maintenance ownership in lock", 3)
    current_paths = set(staged_paths(repo))
    changed: list[str] = []
    for expected in entries:
        if not isinstance(expected, dict) or not isinstance(expected.get("path"), str):
            fail("检查点锁包含无效的暂存路径记录", 3)
        path = expected["path"]
        if path in maintenance:
            continue
        actual = index_entry(repo, path)
        if path not in current_paths or actual.get("mode") != expected.get("mode") or actual.get("blob") != expected.get("blob"):
            changed.append(path)
    if changed:
        rendered = "\n  - ".join(changed)
        fail(f"冻结后的初始暂存内容已变化：\n  - {rendered}", 4)


def command_freeze(args: argparse.Namespace) -> None:
    repo, git_dir, lock_path = resolve_repo(args.repo)
    title = args.title.strip()
    if not title or "\n" in title or "\r" in title:
        fail("冻结标题必须是非空单行文本", 2)
    if lock_path.exists():
        fail("A checkpoint lock already exists", 3)
    branch = ensure_checkpoint_branch(repo)
    if in_progress(repo):
        fail("Unfinished Git operation; cannot freeze", 4)
    entries = initial_entries(repo)
    maintenance = sorted(set(args.maintenance_path))
    config, _ = external.load_config(repo)
    for path in maintenance:
        resolved = external.safe_path(repo, path)
        if path in {external.CONFIG, external.BASELINE} or any(
            resolved == repo / root["path"] or resolved.is_relative_to(repo / root["path"])
            for root in config.get("external_code", [])
        ):
            fail("Governance evidence and external sources cannot be delegated as maintenance documents", 4)
    report, candidate = external.evidence(repo)
    if candidate:
        external.verify_tracked(repo, json.loads(candidate))
    if not entries and not report.get("changed"):
        fail("Neither staged changes nor external-source changes to freeze", 4)
    data: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        "worktree": os.fspath(repo),
        "git_dir": os.fspath(git_dir),
        "base_head": current_head(repo),
        "branch": branch,
        "frozen_title": title,
        "initial_staged": entries,
        "external": report,
        "maintenance_paths": maintenance,
        "sealed_tree": None,
    }
    write_new_lock(lock_path, data)
    if candidate:
        candidate_path, report_path = external.artifact_paths(repo)
        external.write_atomic(candidate_path, candidate)
        external.write_atomic(report_path, external.encode(report))
    emit(
        {
            "event": "snapshot_frozen",
            "base_head": data["base_head"],
            "branch": data["branch"],
            "frozen_title": title,
            "lock_path": os.fspath(lock_path),
            "initial_staged_paths": [entry["path"] for entry in data["initial_staged"]],
            "external": report,
            "maintenance_paths": maintenance,
            "external_artifacts": [str(p) for p in external.artifact_paths(repo)] if candidate else [],
        }
    )


def command_verify(args: argparse.Namespace) -> None:
    repo, _, lock_path = resolve_repo(args.repo)
    data = read_lock(lock_path)
    verify_snapshot(repo, data)
    emit(
        {
            "event": "snapshot_verified",
            "base_head": data["base_head"],
            "branch": data["branch"],
            "frozen_title": data["frozen_title"],
            "lock_path": os.fspath(lock_path),
        }
    )


def command_seal(args: argparse.Namespace) -> None:
    repo, _, lock_path = resolve_repo(args.repo)
    data = read_lock(lock_path)
    verify_snapshot(repo, data)
    verify_governance_tree(repo, data, ":")
    ensure_no_unmerged(repo)
    tree = text_git(repo, "write-tree")
    data["sealed_tree"] = tree
    data["sealed_at"] = utc_now()
    replace_lock(lock_path, data)
    emit(
        {
            "event": "checkpoint_sealed",
            "sealed_tree": tree,
            "frozen_title": data["frozen_title"],
            "lock_path": os.fspath(lock_path),
        }
    )


def command_verify_commit(args: argparse.Namespace) -> None:
    repo, _, lock_path = resolve_repo(args.repo)
    data = read_lock(lock_path)
    validate_external(repo, data, "HEAD")
    verify_governance_tree(repo, data, "HEAD")
    sealed_tree = data.get("sealed_tree")
    if not isinstance(sealed_tree, str) or not sealed_tree:
        fail("检查点尚未 seal，不能验证提交", 4)
    branch = ensure_checkpoint_branch(repo)
    if branch != data.get("branch"):
        fail(f"提交后分支不匹配：期望 {data.get('branch')!r}，实际 {branch!r}", 4)
    commit = current_head(repo)
    base_head = data.get("base_head")
    if commit == base_head:
        fail("HEAD 仍等于 base HEAD，尚未产生新的检查点提交", 4)
    ancestry = text_git(repo, "rev-list", "--parents", "-n", "1", "HEAD").split()
    parents = ancestry[1:]
    if parents != [base_head]:
        fail(f"检查点提交的 parent 不等于 base HEAD：期望唯一 parent {base_head}，实际 {parents}", 4)
    commit_tree = text_git(repo, "rev-parse", "HEAD^{tree}")
    if commit_tree != sealed_tree:
        fail(f"提交 tree 与 sealed tree 不一致：期望 {sealed_tree}，实际 {commit_tree}", 4)
    if text_git(repo, "show", "-s", "--format=%s", "HEAD") != data.get("frozen_title"):
        fail("Commit subject differs from frozen title", 4)
    cleared = False
    if args.clear:
        try:
            lock_path.unlink()
        except OSError as exc:
            fail(f"提交已验证，但无法清除检查点锁 {lock_path}：{exc}", 3)
        cleared = True
    emit(
        {
            "event": "checkpoint_done",
            "commit": commit,
            "frozen_title": data["frozen_title"],
            "sealed_tree": sealed_tree,
            "lock_path": os.fspath(lock_path),
            "lock_cleared": cleared,
        }
    )


def command_show(args: argparse.Namespace) -> None:
    _, _, lock_path = resolve_repo(args.repo)
    data = read_lock(lock_path)
    emit({"event": "checkpoint_lock", "lock_path": os.fspath(lock_path), **data})


def command_abort(args: argparse.Namespace) -> None:
    _, _, lock_path = resolve_repo(args.repo)
    data = read_lock(lock_path)
    try:
        lock_path.unlink()
    except OSError as exc:
        fail(f"无法清除检查点锁 {lock_path}：{exc}", 3)
    emit(
        {
            "event": "checkpoint_aborted",
            "base_head": data.get("base_head"),
            "branch": data.get("branch"),
            "frozen_title": data.get("frozen_title"),
            "lock_path": os.fspath(lock_path),
            "lock_cleared": True,
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("branch-preflight", help="Read-only configured branch normalization")
    preflight.add_argument("--repo", default=".")
    preflight.add_argument("--target", help="New timestamped task branch; optional on existing task branches")
    preflight.set_defaults(handler=command_branch_preflight)

    freeze = subparsers.add_parser("freeze", help="原子创建锁并冻结初始暂存内容")
    freeze.add_argument("--repo", default=".", help="Git 工作树或其中任意目录")
    freeze.add_argument("--title", required=True, help="冻结的单行提交标题")
    freeze.add_argument("--maintenance-path", action="append", default=[],
                        help="Explicit checkpoint-owned document path allowed to change after freeze; repeatable")
    freeze.set_defaults(handler=command_freeze)

    for name, help_text, handler in (
        ("verify", "验证锁、HEAD、分支和初始暂存内容", command_verify),
        ("seal", "验证后记录最终 index tree", command_seal),
        ("show", "显示当前检查点锁", command_show),
        ("abort", "明确放弃检查点并清锁", command_abort),
    ):
        subparser = subparsers.add_parser(name, help=help_text)
        subparser.add_argument("--repo", default=".", help="Git 工作树或其中任意目录")
        subparser.set_defaults(handler=handler)

    verify_commit = subparsers.add_parser("verify-commit", help="验证 HEAD tree 与 sealed tree")
    verify_commit.add_argument("--repo", default=".", help="Git 工作树或其中任意目录")
    verify_commit.add_argument("--clear", action="store_true", help="验证成功后清除锁")
    verify_commit.set_defaults(handler=command_verify_commit)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except (external.SnapshotError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"checkpoint_guard: {exc}", file=sys.stderr)
        return 4
    except GuardError as exc:
        print(f"checkpoint_guard: {exc}", file=sys.stderr)
        return exc.code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
