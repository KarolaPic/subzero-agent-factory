#!/usr/bin/env python3
"""Multi-Identity Git and GitHub Auth Governance Engine.

Enforces cesarchavezcal (cesarchavezcal@gmail.com) as the strict default author
and pusher across external target repositories, manages gh auth switching,
restores prior accounts on exit/failure, and allows .factory.yml overrides.
"""

from __future__ import annotations

import argparse
import atexit
import contextlib
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Generator, Optional, Tuple

logger = logging.getLogger("git_identity")

DEFAULT_GITHUB_USER = "cesarchavezcal"
DEFAULT_GIT_EMAIL = "cesarchavezcal@gmail.com"


class GitIdentityManager:
    """Governs git commit identity and GitHub CLI active authentication."""

    def __init__(self):
        pass

    def parse_active_account(self, auth_status_text: str) -> Optional[str]:
        """Parses output of gh auth status to extract the currently active account."""
        # Find accounts and their active status:
        # e.g.:
        # Logged in to github.com account <USER> ...
        # - Active account: true
        lines = auth_status_text.splitlines()
        current_account = None

        for line in lines:
            acct_match = re.search(r"account\s+([a-zA-Z0-9_\-]+)", line)
            if acct_match:
                current_account = acct_match.group(1).strip()

            if "Active account: true" in line and current_account:
                return current_account

        return None

    def get_active_account(self) -> Optional[str]:
        """Queries gh auth status to determine active user."""
        try:
            res = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                check=False,
            )
            combined = res.stdout + "\n" + res.stderr
            return self.parse_active_account(combined)
        except Exception as e:
            logger.warning("Could not query gh auth status: %s", e)
            return None

    def switch_account(self, user: str, hostname: str = "github.com") -> bool:
        """Switches active GitHub account via gh auth switch."""
        try:
            res = subprocess.run(
                ["gh", "auth", "switch", "--hostname", hostname, "--user", user],
                capture_output=True,
                text=True,
                check=False,
            )
            return res.returncode == 0
        except Exception as e:
            logger.error("Failed to switch gh auth to %s: %s", user, e)
            return False

    def configure_worktree_identity(
        self,
        worktree_path: Path | str,
        user: str,
        email: str,
    ) -> None:
        """Sets local repository identity without altering global user config."""
        path = Path(worktree_path).resolve()
        subprocess.run(["git", "config", "--local", "user.name", user], cwd=path, check=False)
        subprocess.run(["git", "config", "--local", "user.email", email], cwd=path, check=False)

    def resolve_identity(self, adapter: Optional[Any] = None) -> Tuple[str, str]:
        """Resolves target user and email with adapter overrides or default values."""
        target_user = (getattr(adapter, "github_user", None) or DEFAULT_GITHUB_USER).strip()
        target_email = (getattr(adapter, "git_email", None) or DEFAULT_GIT_EMAIL).strip()
        return target_user, target_email


@contextlib.contextmanager
def governed_identity(
    target_user: Optional[str] = None,
    target_email: Optional[str] = None,
    worktree_path: Optional[Path | str] = None,
    manager: Optional[GitIdentityManager] = None,
) -> Generator[Tuple[str, str], None, None]:
    """Context manager switching to target identity and reliably restoring prior state."""
    mgr = manager or GitIdentityManager()
    user = target_user or DEFAULT_GITHUB_USER
    email = target_email or DEFAULT_GIT_EMAIL

    prior_account = mgr.get_active_account()

    if prior_account and prior_account != user:
        logger.info("Switching active gh account: %s -> %s", prior_account, user)
        mgr.switch_account(user)

    if worktree_path:
        mgr.configure_worktree_identity(worktree_path, user, email)

    try:
        yield user, email
    finally:
        if prior_account and prior_account != user:
            logger.info("Restoring previous active gh account: %s", prior_account)
            mgr.switch_account(prior_account)


def main(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Git and GitHub Auth Identity Governance")
    parser.add_argument("--status", action="store_true", help="Print active GitHub account")
    parser.add_argument("--switch", help="Switch active GitHub account to specified user")
    parser.add_argument("--worktree", help="Configure identity in given worktree")

    parsed = parser.parse_args(args)
    mgr = GitIdentityManager()

    if parsed.status:
        active = mgr.get_active_account()
        print(f"Active account: {active}")
        return 0

    if parsed.switch:
        ok = mgr.switch_account(parsed.switch)
        print(f"Switched to {parsed.switch}: {'success' if ok else 'failed'}")
        return 0 if ok else 1

    if parsed.worktree:
        mgr.configure_worktree_identity(parsed.worktree, DEFAULT_GITHUB_USER, DEFAULT_GIT_EMAIL)
        print(f"Configured identity {DEFAULT_GITHUB_USER} in {parsed.worktree}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
