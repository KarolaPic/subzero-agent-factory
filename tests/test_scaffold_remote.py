"""Tests for scripts/scaffold_project.py GitHub remote bootstrap functions."""

from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from scripts.scaffold_project import (
    bootstrap_github_repository,
    configure_project_webhook,
    provision_project_labels,
)


class TestScaffoldRemote(unittest.TestCase):
    @patch("subprocess.run")
    def test_bootstrap_github_repository_dry_run(self, mock_run):
        """Verify dry-run skips subprocess calls."""
        res = bootstrap_github_repository(
            repo_name="demo-app",
            project_path=Path("/tmp/demo-app"),
            public=True,
            dry_run=True,
        )
        self.assertTrue(res["success"])
        self.assertTrue(res["dry_run"])
        mock_run.assert_not_called()

    @patch("scripts.git_identity.governed_identity")
    @patch("subprocess.run")
    def test_bootstrap_github_repository_success(self, mock_run, mock_gov):
        """Verify gh repo create is called with correct flags."""
        mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/cesarchavezcal/demo-app\n", stderr="")

        res = bootstrap_github_repository(
            repo_name="demo-app",
            project_path=Path("/tmp/demo-app"),
            public=True,
            dry_run=False,
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["repo_name"], "demo-app")

        # Verify git init / commit / gh repo create sequence
        call_cmds = [call[0][0] for call in mock_run.call_args_list]
        flattened = [" ".join(cmd) if isinstance(cmd, list) else cmd for cmd in call_cmds]
        self.assertTrue(any("gh repo create" in cmd for cmd in flattened))

    @patch("subprocess.run")
    def test_provision_project_labels(self, mock_run):
        """Verify setup-labels.sh is called with GH_REPO env var."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Labels created", stderr="")

        res = provision_project_labels(repo_slug="cesarchavezcal/demo-app", dry_run=False)
        self.assertTrue(res["success"])
        mock_run.assert_called_once()
        env_passed = mock_run.call_args[1].get("env", {})
        self.assertEqual(env_passed.get("GH_REPO"), "cesarchavezcal/demo-app")

    @patch("subprocess.run")
    def test_configure_project_webhook(self, mock_run):
        """Verify gh api call creates webhook on repository."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Created", stderr="")

        res = configure_project_webhook(
            repo_slug="cesarchavezcal/demo-app",
            webhook_url="https://factory.example.com/webhook",
            dry_run=False,
        )
        self.assertTrue(res["success"])
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertIn("api", cmd)
        self.assertIn("repos/cesarchavezcal/demo-app/hooks", cmd)


if __name__ == "__main__":
    unittest.main()
