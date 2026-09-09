#!/usr/bin/env python3
"""Fingerprint configured external source trees; check and discover are read-only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile

CONFIG = '.agents/repo-governance.json'
BASELINE = '.agents/external-code.snapshot.json'
VCS = {'.git', '.hg', '.svn'}


class SnapshotError(RuntimeError):
    pass


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True)
    if result.returncode:
        raise SnapshotError(result.stderr.decode('utf-8', 'replace').strip())
    return result.stdout


def repo_root(value: str) -> Path:
    return Path(git(Path(value), 'rev-parse', '--show-toplevel').decode().strip()).resolve()


def encode(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + '\n').encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative(value: object) -> str:
    if not isinstance(value, str) or not value or '\\' in value:
        raise SnapshotError(f'Expected a repository-relative POSIX path: {value!r}')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or value != path.as_posix() or value == '.':
        raise SnapshotError(f'Unsafe or non-canonical relative path: {value!r}')
    if any(part in VCS for part in path.parts):
        raise SnapshotError(f'VCS metadata cannot be registered: {value}')
    return value


def safe_path(repo: Path, value: str) -> Path:
    path = repo / relative(value)
    current = repo
    for part in Path(value).parts:
        current /= part
        if current.is_symlink():
            raise SnapshotError(f'Configured paths must not traverse symlinks: {value}')
    if not path.resolve().is_relative_to(repo):
        raise SnapshotError(f'Path escapes repository: {value}')
    return path


def load_config(repo: Path) -> tuple[dict, str | None]:
    path = safe_path(repo, CONFIG)
    if not path.exists():
        return {'version': 1, 'external_code': [], 'branches': {}}, None
    raw = path.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get('version') != 1:
        raise SnapshotError('Unsupported repo-governance config version')
    if set(data) - {'version', 'external_code', 'branches'}:
        raise SnapshotError('Unknown repo-governance config field')
    roots = data.get('external_code', [])
    if not isinstance(roots, list):
        raise SnapshotError('external_code must be a list')
    seen = []
    ids = set()
    for root in roots:
        if not isinstance(root, dict) or set(root) - {'id', 'path', 'exclude', 'docs'}:
            raise SnapshotError('Invalid external_code entry')
        if not isinstance(root.get('id'), str) or not root['id'].strip() or root['id'] in ids:
            raise SnapshotError('External root IDs must be nonempty and unique')
        ids.add(root['id'])
        path = safe_path(repo, relative(root.get('path')))
        if path == repo / '.agents' or path in (repo / CONFIG).parents:
            raise SnapshotError('External roots cannot contain governance metadata')
        if any(path == old or path.is_relative_to(old) or old.is_relative_to(path) for old in seen):
            raise SnapshotError('External roots must not overlap')
        seen.append(path)
        for key in ('exclude', 'docs'):
            values = root.get(key, [])
            if not isinstance(values, list):
                raise SnapshotError(f'{key} must be a list')
            for value in values:
                relative(value)
                if key == 'docs':
                    safe_path(repo, value)
    for root in roots:
        for route in root.get('docs', []):
            doc = safe_path(repo, route)
            if any(doc == source or doc.is_relative_to(source) for source in seen):
                raise SnapshotError('Review documents must live outside frozen external roots')
    branches = data.get('branches', {})
    if not isinstance(branches, dict) or set(branches) - {'protected', 'base', 'task_prefix'}:
        raise SnapshotError('Invalid branches policy')
    protected = branches.get('protected', [])
    if not isinstance(protected, list) or any(not isinstance(x, str) or not x for x in protected):
        raise SnapshotError('branches.protected must list exact branch names')
    for branch in protected + ([branches['base']] if branches.get('base') else []):
        git(repo, 'check-ref-format', 'refs/heads/' + branch)
    prefix = branches.get('task_prefix', 'feature/')
    if not isinstance(prefix, str) or not prefix or not prefix.endswith('/'):
        raise SnapshotError('task_prefix must be a nonempty prefix ending in /')
    git(repo, 'check-ref-format', 'refs/heads/' + prefix + '20000101-000000')
    return data, digest(raw)


def scan(repo: Path, config: dict) -> dict:
    entries = {}
    root_records = []
    for root in sorted(config.get('external_code', []), key=lambda x: x['id']):
        base = safe_path(repo, root['path'])
        if not base.is_dir():
            raise SnapshotError(f'Configured external directory is missing: {root["path"]}')
        excluded = root.get('exclude', [])
        root_records.append({'id': root['id'], 'path': root['path'], 'exclude': sorted(excluded)})
        def walk(directory: Path) -> None:
            for path in sorted(directory.iterdir()):
                local = path.relative_to(base).as_posix()
                if path.name in VCS or any(local == x or local.startswith(x + '/') for x in excluded):
                    continue
                before = path.lstat()
                mode = before.st_mode
                name = path.relative_to(repo).as_posix()
                if stat.S_ISLNK(mode):
                    content_hash = digest(os.fsencode(os.readlink(path)))
                    kind = 'symlink'
                elif stat.S_ISDIR(mode):
                    walk(path)
                    continue
                elif stat.S_ISREG(mode):
                    hasher = hashlib.sha256()
                    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
                    with os.fdopen(os.open(path, flags), 'rb') as stream:
                        opened = os.fstat(stream.fileno())
                        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                            raise SnapshotError(f'File changed during scan: {name}')
                        for block in iter(lambda: stream.read(1024 * 1024), b''):
                            hasher.update(block)
                    content_hash = hasher.hexdigest()
                    kind = 'file'
                else:
                    raise SnapshotError(f'Unsupported special file in external source: {name}')
                after = path.lstat()
                identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
                if identity(before) != identity(after):
                    raise SnapshotError(f'File changed during scan: {name}')
                entries[name] = {'root': root['id'], 'kind': kind, 'sha256': content_hash,
                                 'executable': bool(mode & 0o111) if kind == 'file' else False}
        walk(base)
    return {'version': 1, 'roots': root_records, 'files': entries}


def evidence(repo: Path) -> tuple[dict, bytes | None]:
    config, config_sha = load_config(repo)
    if not config.get('external_code'):
        return {'config_sha256': config_sha, 'enabled': False, 'changed': False}, None
    candidate = scan(repo, config)
    baseline_path = safe_path(repo, BASELINE)
    if not baseline_path.is_file():
        raise SnapshotError('Missing external baseline; perform a full source review, then snapshot --reviewed')
    baseline_bytes = baseline_path.read_bytes()
    baseline = json.loads(baseline_bytes)
    if not isinstance(baseline, dict) or baseline.get('version') != 1 or not isinstance(baseline.get('files'), dict):
        raise SnapshotError('Invalid external baseline')
    old, new = baseline['files'], candidate['files']
    added = sorted(new.keys() - old.keys())
    deleted = sorted(old.keys() - new.keys())
    modified = sorted(p for p in old.keys() & new.keys() if old[p] != new[p])
    roots = sorted({new[p]['root'] for p in added + modified} | {old[p]['root'] for p in deleted + modified})
    content = encode(candidate)
    return {'config_sha256': config_sha, 'enabled': True,
            'changed': baseline != candidate, 'candidate_sha256': digest(content),
            'baseline_sha256': digest(baseline_bytes), 'baseline': BASELINE,
            'added': added, 'modified': modified, 'deleted': deleted,
            'roots': roots, 'scope_changed': baseline.get('roots') != candidate['roots']}, content


def verify_tracked(repo: Path, manifest: dict, tree: str | None = None) -> None:
    """A tracked source blob must agree with the same checkpoint's live fingerprint."""
    roots = manifest['roots']
    raw = git(repo, 'ls-tree', '-r', '-z', tree) if tree else git(repo, 'ls-files', '--stage', '-z')
    for record in raw.split(b'\0'):
        if not record:
            continue
        metadata, path_bytes = record.split(b'\t', 1)
        fields = metadata.decode('ascii').split()
        mode, blob = (fields[0], fields[2]) if tree else (fields[0], fields[1])
        name = os.fsdecode(path_bytes)
        if mode == '160000' and any(r['path'].startswith(name + '/') for r in roots):
            raise SnapshotError(f'External root is inside submodule {name}; review that repository separately')
        root = next((r for r in roots if name == r['path'] or name.startswith(r['path'] + '/')), None)
        if root is None:
            continue
        local = name[len(root['path']):].lstrip('/')
        if any(part in VCS for part in PurePosixPath(local).parts) or any(
            local == x or local.startswith(x + '/') for x in root['exclude']
        ):
            continue
        if mode == '160000':
            raise SnapshotError(f'Submodule gitlink {name}: review its pinned repository separately, not as a copied source root')
        entry = manifest['files'].get(name)
        if entry is None:
            raise SnapshotError(f'Tracked external file is absent from live snapshot: {name}')
        hasher = hashlib.sha256()
        with subprocess.Popen(['git', '-C', str(repo), 'cat-file', 'blob', blob], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
            for block in iter(lambda: process.stdout.read(1024 * 1024), b''):
                hasher.update(block)
            process.stdout.close()
            if process.wait():
                raise SnapshotError(f'Cannot read tracked blob: {name}')
        kind = 'symlink' if mode == '120000' else 'file'
        if (entry['sha256'] != hasher.hexdigest() or entry['kind'] != kind
                or entry['executable'] != (mode == '100755')):
            raise SnapshotError(f'Tracked external file differs from {tree or "index"}: {name}; resolve scope and refreeze, do not stage later work implicitly')


def write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def artifact_paths(repo: Path) -> tuple[Path, Path]:
    directory = Path(git(repo, 'rev-parse', '--absolute-git-dir').decode().strip())
    return directory / 'external-code.candidate.json', directory / 'external-code.changes.json'


def discover(repo: Path) -> dict:
    names = {'vendor', 'third_party', 'third-party', 'external', 'extern', 'deps'}
    skip = VCS | {'node_modules', '.venv', 'venv', '__pycache__', 'build', 'dist', 'target', 'install', 'log'}
    found = []
    for directory, children, _ in os.walk(repo, followlinks=False):
        base = Path(directory)
        children[:] = sorted(n for n in children if n not in skip and not (base / n).is_symlink())
        if len(base.relative_to(repo).parts) >= 4:
            children[:] = []
        for name in list(children):
            path = base / name
            if name.lower() in names:
                rel = path.relative_to(repo).as_posix()
                ignored = subprocess.run(['git', '-C', str(repo), 'check-ignore', '-q', '--', rel]).returncode == 0
                found.append({'path': rel, 'reason': 'conventional directory name', 'ignored': ignored})
                children.remove(name)
    return {'event': 'external_code_candidates', 'candidates': found,
            'limitations': 'Names only, depth <= 4; inspect manifests, submodules, ignore rules and project docs separately. No roots registered.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['discover', 'check', 'snapshot', 'accept'])
    parser.add_argument('--repo', default='.')
    parser.add_argument('--write-artifacts', action='store_true', help='check only: write per-worktree candidate/report')
    parser.add_argument('--reviewed', action='store_true', help='snapshot only: full initial review is complete')
    parser.add_argument('--expected-sha256', help='accept only: frozen candidate digest')
    args = parser.parse_args()
    try:
        repo = repo_root(args.repo)
        if args.command == 'discover':
            print(json.dumps(discover(repo), indent=2))
            return 0
        if args.command == 'snapshot':
            if not args.reviewed:
                raise SnapshotError('Initial snapshot requires --reviewed after a full source review')
            config, _ = load_config(repo)
            if not config.get('external_code'):
                raise SnapshotError('No external roots registered')
            path = safe_path(repo, BASELINE)
            if path.exists():
                raise SnapshotError('Baseline already exists; use the frozen accept workflow')
            content = encode(scan(repo, config))
            write_atomic(path, content)
            print(json.dumps({'event': 'external_snapshot_created', 'sha256': digest(content)}))
            return 0
        report, content = evidence(repo)
        if args.command == 'accept':
            lock_path = Path(git(repo, 'rev-parse', '--absolute-git-dir').decode().strip()) / 'agent-checkpoint.lock'
            lock = json.loads(lock_path.read_bytes())
            frozen = lock.get('external', {})
            if (lock.get('schema_version') != 2 or not content or not frozen.get('enabled')
                    or not args.expected_sha256 or report['candidate_sha256'] != args.expected_sha256
                    or frozen.get('candidate_sha256') != args.expected_sha256
                    or report['config_sha256'] != frozen.get('config_sha256')
                    or report['baseline_sha256'] not in {frozen.get('baseline_sha256'), args.expected_sha256}):
                raise SnapshotError('Acceptance does not match frozen external evidence')
            head = git(repo, 'rev-parse', 'HEAD').decode().strip()
            branch = git(repo, 'symbolic-ref', '--quiet', '--short', 'HEAD').decode().strip()
            if head != lock.get('base_head') or branch != lock.get('branch'):
                raise SnapshotError('Checkpoint identity changed before acceptance')
            write_atomic(safe_path(repo, BASELINE), content)
            print(json.dumps({'event': 'external_snapshot_accepted', 'sha256': args.expected_sha256}))
            return 0
        if args.write_artifacts and content:
            candidate_path, report_path = artifact_paths(repo)
            report.update(candidate=str(candidate_path), report=str(report_path))
            write_atomic(candidate_path, content)
            write_atomic(report_path, encode(report))
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 3 if report['changed'] else 0
    except (SnapshotError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'event': 'external_snapshot_error', 'error': str(exc)}), file=sys.stderr)
        return 4


if __name__ == '__main__':
    raise SystemExit(main())
