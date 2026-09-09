"""Behavioral tests use disposable Git repositories, never the user's worktree."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/save-checkpoint/scripts'
GUARD = SCRIPTS / 'checkpoint_guard.py'
SNAPSHOT = SCRIPTS / 'external_snapshot.py'
CONFIG = '.agents/repo-governance.json'
BASELINE = '.agents/external-code.snapshot.json'


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        self.write('source.txt', 'initial\n')
        self.git('add', 'source.txt')
        self.git('commit', '-m', 'initial')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True).stdout.decode().strip()

    def write(self, name, content):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def tool(self, script, command, *args, code=0):
        result = subprocess.run([sys.executable, str(script), command, '--repo', str(self.repo), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout) if result.stdout else {}

    def config(self, **kwargs):
        self.write(CONFIG, json.dumps({'version': 1, **kwargs}) + '\n')

    def setup_external(self):
        self.config(external_code=[{'id': 'sdk', 'path': 'third_party/sdk', 'exclude': ['build'], 'docs': ['docs/sdk.md']},
                                   {'id': 'legacy', 'path': 'external/legacy'}])
        self.write('.gitignore', 'third_party/\nexternal/\n')
        self.write('third_party/sdk/a.c', 'a\n')
        self.write('external/legacy/b.py', 'b\n')
        self.tool(SNAPSHOT, 'snapshot', '--reviewed')
        self.git('add', CONFIG, BASELINE, '.gitignore')
        self.git('commit', '-m', 'register external sources')

    def stage_change(self):
        self.write('source.txt', 'updated\n')
        self.git('add', 'source.txt')

    def test_legacy_without_config(self):
        self.stage_change()
        self.tool(GUARD, 'freeze', '--title', '保存变更')
        self.tool(GUARD, 'verify')
        self.tool(GUARD, 'seal')
        self.git('commit', '-m', '保存变更')
        self.tool(GUARD, 'verify-commit', '--clear')
        self.assertFalse((self.repo / '.git/agent-checkpoint.lock').exists())

    def test_no_changes_rejected(self):
        self.tool(GUARD, 'freeze', '--title', 'empty', code=4)

    def test_multi_roots_changes_and_pure_check(self):
        self.setup_external()
        self.write('third_party/sdk/a.c', 'changed')
        self.write('external/legacy/new.py', 'new')
        (self.repo / 'external/legacy/b.py').unlink()
        report = self.tool(SNAPSHOT, 'check', code=3)
        self.assertEqual(report['modified'], ['third_party/sdk/a.c'])
        self.assertEqual(report['added'], ['external/legacy/new.py'])
        self.assertEqual(report['deleted'], ['external/legacy/b.py'])
        self.assertEqual(report['roots'], ['legacy', 'sdk'])
        self.assertFalse((self.repo / '.git/external-code.candidate.json').exists())

    def test_external_only_checkpoint_and_unstaged_work(self):
        self.setup_external()
        self.write('third_party/sdk/a.c', 'new')
        frozen = self.tool(GUARD, 'freeze', '--title', '审查外部源码')
        self.assertEqual(frozen['initial_staged_paths'], [])
        self.write('source.txt', 'later unstaged work')
        self.tool(GUARD, 'seal', code=4)
        self.tool(SNAPSHOT, 'accept', '--expected-sha256', frozen['external']['candidate_sha256'])
        self.tool(GUARD, 'seal', code=4)  # Accepted but not staged.
        self.git('add', BASELINE)
        self.tool(GUARD, 'verify')
        self.tool(GUARD, 'seal')
        self.git('commit', '-m', '审查外部源码')
        self.tool(GUARD, 'verify-commit', '--clear')
        self.assertIn('source.txt', self.git('diff', '--name-only'))

    def test_external_drift_blocks_verify_accept_and_seal(self):
        self.setup_external()
        self.stage_change()
        frozen = self.tool(GUARD, 'freeze', '--title', 'frozen')
        self.write('third_party/sdk/a.c', 'drift')
        self.tool(GUARD, 'verify', code=4)
        self.tool(GUARD, 'seal', code=4)
        self.tool(SNAPSHOT, 'accept', '--expected-sha256', frozen['external']['candidate_sha256'], code=4)
        self.assertTrue((self.repo / '.git/agent-checkpoint.lock').exists())

    def test_config_drift_rejected(self):
        self.setup_external()
        self.stage_change()
        self.tool(GUARD, 'freeze', '--title', 'frozen')
        self.config(external_code=[])
        self.tool(GUARD, 'verify', code=4)

    def test_unstaged_config_blocks_seal(self):
        self.config(external_code=[])
        self.stage_change()
        self.tool(GUARD, 'freeze', '--title', 'frozen')
        self.tool(GUARD, 'seal', code=4)

    def test_frozen_staged_content_cannot_change_at_seal(self):
        self.stage_change()
        self.tool(GUARD, 'freeze', '--title', 'frozen')
        self.write('source.txt', 'replaced')
        self.git('add', 'source.txt')
        self.tool(GUARD, 'seal', code=4)

    def test_wrong_commit_title_rejected(self):
        self.stage_change()
        self.tool(GUARD, 'freeze', '--title', 'expected')
        self.tool(GUARD, 'seal')
        self.git('commit', '-m', 'wrong')
        self.tool(GUARD, 'verify-commit', '--clear', code=4)
        self.assertTrue((self.repo / '.git/agent-checkpoint.lock').exists())

    def test_protected_branch_and_dirty_base(self):
        self.config(branches={'protected': ['main', 'dev'], 'base': 'dev', 'task_prefix': 'work/'})
        self.git('add', CONFIG)
        self.git('commit', '-m', 'policy')
        self.git('branch', 'dev')
        self.stage_change()
        self.tool(GUARD, 'freeze', '--title', 'bad', code=4)
        result = self.tool(GUARD, 'branch-preflight', '--target', 'work/20260909-120000')
        self.assertEqual(result['action'], 'switch_base_then_create')
        self.git('switch', 'dev')
        result = self.tool(GUARD, 'branch-preflight', '--target', 'work/20260909-120000')
        self.assertEqual(result['action'], 'create_from_base_carry_state')
        self.tool(GUARD, 'branch-preflight', '--target', 'work/not-a-timestamp', code=4)
        self.git('switch', '-c', 'custom-existing-name')
        self.assertEqual(self.tool(GUARD, 'branch-preflight')['action'], 'continue_current_branch')
        self.tool(GUARD, 'freeze', '--title', 'allowed')

    def test_dirty_different_base_stops(self):
        self.config(branches={'protected': ['main', 'dev'], 'base': 'dev'})
        self.git('add', CONFIG)
        self.git('commit', '-m', 'policy')
        self.git('branch', 'dev')
        self.stage_change()
        self.git('commit', '-m', 'main only')
        self.write('untracked', 'dirty')
        self.tool(GUARD, 'branch-preflight', '--target', 'feature/20260909-120000', code=4)

    def test_missing_baseline_and_root_fail(self):
        self.config(external_code=[{'id': 'sdk', 'path': 'third_party/sdk'}])
        self.write('third_party/sdk/a.c', 'a')
        self.tool(SNAPSHOT, 'check', code=4)
        self.tool(SNAPSHOT, 'snapshot', code=4)
        self.tool(SNAPSHOT, 'snapshot', '--reviewed')
        self.tool(SNAPSHOT, 'snapshot', '--reviewed', code=4)
        (self.repo / 'third_party/sdk').rename(self.repo / 'third_party/moved')
        self.tool(SNAPSHOT, 'check', code=4)

    def test_paths_overlap_escape_and_symlink_roots_rejected(self):
        self.write('sdk/a', 'a')
        for roots in ([{'id': 'x', 'path': '../outside'}],
                      [{'id': 'x', 'path': 'sdk'}, {'id': 'y', 'path': 'sdk/nested'}],
                      [{'id': 'x', 'path': '.agents'}]):
            self.config(external_code=roots)
            self.tool(SNAPSHOT, 'check', code=4)
        (self.repo / 'alias').symlink_to(self.repo / 'sdk', target_is_directory=True)
        self.config(external_code=[{'id': 'x', 'path': 'alias'}])
        self.tool(SNAPSHOT, 'check', code=4)

    def test_exclusions_symlinks_and_executable(self):
        self.setup_external()
        self.write('third_party/sdk/build/generated', 'ignored')
        self.tool(SNAPSHOT, 'check')
        link = self.repo / 'third_party/sdk/link'
        link.symlink_to('/missing/outside')
        report = self.tool(SNAPSHOT, 'check', code=3)
        self.assertIn('third_party/sdk/link', report['added'])
        os.chmod(self.repo / 'external/legacy/b.py', 0o755)
        report = self.tool(SNAPSHOT, 'check', code=3)
        self.assertIn('external/legacy/b.py', report['modified'])

    def test_linked_worktree_artifacts_and_lifecycle(self):
        self.setup_external()
        original = self.repo
        linked = Path(self.temp.name) / 'linked'
        self.git('worktree', 'add', '-b', 'linked-task', str(linked))
        self.repo = linked
        self.write('third_party/sdk/a.c', 'a\n')
        self.write('external/legacy/b.py', 'b\n')
        self.stage_change()
        frozen = self.tool(GUARD, 'freeze', '--title', 'linked checkpoint')
        self.assertTrue((linked / '.git').is_file())
        self.assertTrue(all(Path(p).is_file() for p in frozen['external_artifacts']))
        self.assertTrue(all(str(original / '.git/worktrees') in p for p in frozen['external_artifacts']))
        self.tool(GUARD, 'seal')
        self.git('commit', '-m', 'linked checkpoint')
        self.tool(GUARD, 'verify-commit', '--clear')

    def test_discovery_does_not_register_or_scan_generated(self):
        self.write('src/vendor/a', 'a')
        self.write('node_modules/vendor/a', 'a')
        self.write('third_party/sdk/a', 'a')
        result = self.tool(SNAPSHOT, 'discover')
        self.assertEqual({x['path'] for x in result['candidates']}, {'src/vendor', 'third_party'})
        self.assertFalse((self.repo / CONFIG).exists())

    def test_special_file_rejected_without_blocking(self):
        self.setup_external()
        os.mkfifo(self.repo / 'third_party/sdk/pipe')
        self.tool(SNAPSHOT, 'check', code=4)

    def test_scope_removal_preserves_deleted_evidence(self):
        self.setup_external()
        self.config(external_code=[{'id': 'sdk', 'path': 'third_party/sdk', 'exclude': ['build']}])
        self.git('add', CONFIG)
        report = self.tool(SNAPSHOT, 'check', code=3)
        self.assertTrue(report['scope_changed'])
        self.assertEqual(report['deleted'], ['external/legacy/b.py'])
        self.assertIn('legacy', report['roots'])
        frozen = self.tool(GUARD, 'freeze', '--title', 'retire legacy coverage')
        self.tool(SNAPSHOT, 'accept', '--expected-sha256', frozen['external']['candidate_sha256'])
        self.git('add', BASELINE)
        self.tool(GUARD, 'seal')

    def test_baseline_tamper_after_freeze_fails(self):
        self.setup_external()
        self.stage_change()
        self.tool(GUARD, 'freeze', '--title', 'frozen')
        path = self.repo / BASELINE
        path.write_text(path.read_text() + ' ')
        self.tool(GUARD, 'verify', code=4)

    def test_external_drift_after_commit_preserves_lock(self):
        self.setup_external()
        self.stage_change()
        self.tool(GUARD, 'freeze', '--title', 'frozen')
        self.tool(GUARD, 'seal')
        self.git('commit', '-m', 'frozen')
        self.write('external/legacy/b.py', 'late drift')
        self.tool(GUARD, 'verify-commit', '--clear', code=4)
        self.assertTrue((self.repo / '.git/agent-checkpoint.lock').exists())

    def test_review_docs_cannot_be_in_frozen_sources(self):
        self.write('sdk/a', 'a')
        self.config(external_code=[{'id': 'sdk', 'path': 'sdk', 'docs': ['sdk/review.md']}])
        self.tool(SNAPSHOT, 'check', code=4)

    def test_base_owned_by_other_worktree_stops(self):
        self.config(branches={'protected': ['main', 'dev'], 'base': 'dev'})
        self.git('add', CONFIG)
        self.git('commit', '-m', 'policy')
        self.git('worktree', 'add', '-b', 'dev', str(Path(self.temp.name) / 'base-worktree'))
        self.tool(GUARD, 'branch-preflight', '--target', 'feature/20260909-120000', code=4)

    def test_detached_and_unfinished_operation_rejected(self):
        self.stage_change()
        self.git('checkout', '--detach')
        self.tool(GUARD, 'freeze', '--title', 'detached', code=4)
        self.git('switch', 'main')
        self.write('.git/CHERRY_PICK_HEAD', self.git('rev-parse', 'HEAD'))
        self.tool(GUARD, 'branch-preflight', code=4)
        self.tool(GUARD, 'freeze', '--title', 'unfinished', code=4)

    def test_explicit_document_ownership_allows_initial_doc_maintenance(self):
        self.write('docs/guide.md', 'last_reviewed_commit_title: null')
        self.git('add', 'docs/guide.md')
        self.stage_change()
        frozen = self.tool(GUARD, 'freeze', '--title', 'initialize docs', '--maintenance-path', 'docs/guide.md')
        self.assertEqual(frozen['maintenance_paths'], ['docs/guide.md'])
        self.write('docs/guide.md', 'last_reviewed_commit_title: initialize docs')
        self.git('add', 'docs/guide.md')
        self.tool(GUARD, 'verify')
        self.tool(GUARD, 'seal')
        self.git('commit', '-m', 'initialize docs')
        self.tool(GUARD, 'verify-commit', '--clear')

    def test_evidence_cannot_be_delegated_as_document(self):
        self.setup_external()
        self.stage_change()
        for path in [CONFIG, BASELINE, 'third_party/sdk/a.c']:
            self.tool(GUARD, 'freeze', '--title', 'bad', '--maintenance-path', path, code=4)

    def test_tracked_external_partial_staging_rejected(self):
        self.setup_external()
        self.git('add', '-f', 'third_party/sdk/a.c')
        self.git('commit', '-m', 'track sdk')
        self.write('third_party/sdk/a.c', 'staged version')
        self.git('add', '-f', 'third_party/sdk/a.c')
        self.write('third_party/sdk/a.c', 'later unstaged version')
        self.tool(GUARD, 'freeze', '--title', 'inconsistent', code=4)
        self.assertFalse((self.repo / '.git/agent-checkpoint.lock').exists())

    def test_tracked_external_matching_snapshot_succeeds(self):
        self.setup_external()
        self.git('add', '-f', 'third_party/sdk/a.c')
        self.git('commit', '-m', 'track sdk')
        self.write('third_party/sdk/a.c', 'updated sdk')
        self.git('add', '-f', 'third_party/sdk/a.c')
        frozen = self.tool(GUARD, 'freeze', '--title', 'update sdk')
        self.tool(SNAPSHOT, 'accept', '--expected-sha256', frozen['external']['candidate_sha256'])
        self.git('add', BASELINE)
        self.tool(GUARD, 'seal')
        self.git('commit', '-m', 'update sdk')
        self.tool(GUARD, 'verify-commit', '--clear')

    def test_old_lock_rejected(self):
        self.write('.git/agent-checkpoint.lock', '{"schema_version": 1}')
        self.tool(GUARD, 'verify', code=3)


if __name__ == '__main__':
    unittest.main()
