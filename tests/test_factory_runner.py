"""Unit and integration tests for External Core Factory WorktreeManager & factory_runner.py."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.factory_runner import WorktreeManager, parse_args, run_cli


class TestWorktreeManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name) / "factory_worktrees"
        self.manager = WorktreeManager(base_dir=self.base_dir)

        # Create a mock git repository for testing
        self.repo_dir = Path(self.temp_dir.name) / "mock_repo"
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-b", "main"], cwd=self.repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo_dir, check=True)
        (self.repo_dir / "README.md").write_text("# Test Repo\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_dir, check=True, capture_output=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_worktree_path_resolution(self):
        """Resolves target path under ~/.factory/worktrees/<repo-slug>/<issue-id>."""
        path = self.manager.get_worktree_path(repo_slug="owner/project", issue_id=105)
        expected = self.base_dir / "owner/project" / "105"
        self.assertEqual(path, expected)

    def test_create_and_cleanup_worktree(self):
        """Creates an isolated git worktree and cleans it up cleanly."""
        repo_slug = "test-owner/mock-repo"
        issue_id = 105
        branch = "feat/105-test"

        wt_path = self.manager.create_worktree(
            repo_path=self.repo_dir,
            branch=branch,
            issue_id=issue_id,
            repo_slug=repo_slug,
        )

        self.assertTrue(wt_path.exists())
        self.assertTrue((wt_path / "README.md").exists())
        self.assertTrue((wt_path / ".git").exists())

        # Cleanup
        self.manager.cleanup_worktree(wt_path, repo_path=self.repo_dir)
        self.assertFalse(wt_path.exists())

    def test_dry_run_does_not_modify_filesystem(self):
        """Dry-run mode prints intent without creating worktree directory."""
        dry_manager = WorktreeManager(base_dir=self.base_dir, dry_run=True)
        wt_path = dry_manager.create_worktree(
            repo_path=self.repo_dir,
            branch="feat/dry-run",
            issue_id=999,
            repo_slug="test-owner/dry-repo",
        )
        self.assertFalse(wt_path.exists())

    def test_cli_argument_parsing(self):
        """Validates CLI flags: --repo, --issue, --branch, --dry-run."""
        args = parse_args(["--repo", "owner/repo", "--issue", "105", "--branch", "feat/105-worktree", "--dry-run"])
        self.assertEqual(args.repo, "owner/repo")
        self.assertEqual(args.issue, "105")
        self.assertEqual(args.branch, "feat/105-worktree")
        self.assertTrue(args.dry_run)

    def test_exit_trap_registration(self):
        """Confirms cleanup handler is registered for active worktree."""
        self.manager.register_active_worktree(self.base_dir / "test/path", self.repo_dir)
        self.assertIn(str(self.base_dir / "test/path"), self.manager.active_worktrees)
        self.manager.unregister_active_worktree(self.base_dir / "test/path")
        self.assertNotIn(str(self.base_dir / "test/path"), self.manager.active_worktrees)


if __name__ == "__main__":
    unittest.main()
