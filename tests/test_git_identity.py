"""Unit tests for External Core Factory Git and GitHub auth identity manager."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.git_identity import (
    DEFAULT_GIT_EMAIL,
    DEFAULT_GITHUB_USER,
    GitIdentityManager,
    governed_identity,
)


class TestGitIdentityManager(unittest.TestCase):
    def setUp(self):
        self.manager = GitIdentityManager()

    def test_default_identity_constants(self):
        """Verifies default identity is cesarchavezcal and cesarchavezcal@gmail.com."""
        self.assertEqual(DEFAULT_GITHUB_USER, "cesarchavezcal")
        self.assertEqual(DEFAULT_GIT_EMAIL, "cesarchavezcal@gmail.com")

    def test_parse_active_account_from_auth_status(self):
        """Correctly extracts the active github account from gh auth status text."""
        sample_output = """
        github.com
          ✓ Logged in to github.com account ace-cesar-c (keyring)
          - Active account: false
          ✓ Logged in to github.com account cesarchavezcal (keyring)
          - Active account: true
        """
        active = self.manager.parse_active_account(sample_output)
        self.assertEqual(active, "cesarchavezcal")

    def test_parse_active_account_when_first_is_active(self):
        sample_output = """
        github.com
          ✓ Logged in to github.com account ace-cesar-c (keyring)
          - Active account: true
          ✓ Logged in to github.com account cesarchavezcal (keyring)
          - Active account: false
        """
        active = self.manager.parse_active_account(sample_output)
        self.assertEqual(active, "ace-cesar-c")

    def test_resolve_identity_with_adapter_overrides(self):
        """Allows .factory.yml adapter overrides for custom organization accounts."""
        mock_adapter = MagicMock()
        mock_adapter.github_user = "acme-bot"
        mock_adapter.git_email = "bot@acme.corp"

        user, email = self.manager.resolve_identity(mock_adapter)
        self.assertEqual(user, "acme-bot")
        self.assertEqual(email, "bot@acme.corp")

        # Without overrides
        mock_empty_adapter = MagicMock()
        mock_empty_adapter.github_user = None
        mock_empty_adapter.git_email = None

        user, email = self.manager.resolve_identity(mock_empty_adapter)
        self.assertEqual(user, DEFAULT_GITHUB_USER)
        self.assertEqual(email, DEFAULT_GIT_EMAIL)

    @patch.object(GitIdentityManager, "get_active_account")
    @patch.object(GitIdentityManager, "switch_account")
    def test_governed_identity_context_manager_restores_prior_account(
        self, mock_switch, mock_get_active
    ):
        """Context manager switches to target user and guarantees restoration on exit."""
        mock_get_active.return_value = "ace-cesar-c"

        with governed_identity(target_user="cesarchavezcal", manager=self.manager):
            mock_switch.assert_called_with("cesarchavezcal")

        # After block exit, previous account must be restored
        mock_switch.assert_called_with("ace-cesar-c")

    @patch.object(GitIdentityManager, "get_active_account")
    @patch.object(GitIdentityManager, "switch_account")
    def test_governed_identity_restores_prior_account_on_exception(
        self, mock_switch, mock_get_active
    ):
        """Context manager restores prior account even when an unhandled exception occurs."""
        mock_get_active.return_value = "ace-cesar-c"

        with self.assertRaises(RuntimeError):
            with governed_identity(target_user="cesarchavezcal", manager=self.manager):
                raise RuntimeError("Simulated build failure")

        mock_switch.assert_called_with("ace-cesar-c")


if __name__ == "__main__":
    unittest.main()
