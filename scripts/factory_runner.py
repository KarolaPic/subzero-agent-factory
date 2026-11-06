#!/usr/bin/env python3
"""External Core Factory Runner & Worktree Manager.

Orchestrates execution of external target projects inside dedicated worktrees
under ~/.factory/worktrees/<repo-slug>/<issue-id>.
Handles creation, isolation, exit cleanup traps, and error recovery.
"""

from __future__ import annotations

import argparse
import atexit
import logging
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("factory_runner")


class WorktreeManager:
    """Manages isolated git worktree environments for target projects."""

    def __init__(self, base_dir: Optional[Path | str] = None, dry_run: bool = False):
        if base_dir is None:
            env_base = os.environ.get("FACTORY_WORKTREES_DIR")
            self.base_dir = Path(env_base).resolve() if env_base else Path.home() / ".factory" / "worktrees"
        else:
            self.base_dir = Path(base_dir).resolve()

        self.dry_run = dry_run
        self.active_worktrees: Dict[str, str] = {}
        self._trap_registered = False

    def _setup_exit_traps(self) -> None:
        if self._trap_registered:
            return

        atexit.register(self._cleanup_all_active)

        def _signal_handler(signum, frame):
            logger.warning("Received signal %s, cleaning up active worktrees...", signum)
            self._cleanup_all_active()
            sys.exit(128 + signum)

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, _signal_handler)
            except (ValueError, AttributeError):
                # Signals may not be supported in some thread/test contexts
                pass

        self._trap_registered = True

    def _cleanup_all_active(self) -> None:
        worktrees = list(self.active_worktrees.items())
        for wt_path, repo_path in worktrees:
            try:
                self.cleanup_worktree(wt_path, repo_path, force=True)
            except Exception as e:
                logger.error("Failed to cleanup worktree %s: %s", wt_path, e)

    def register_active_worktree(self, worktree_path: Path | str, repo_path: Path | str) -> None:
        self.active_worktrees[str(Path(worktree_path).resolve())] = str(Path(repo_path).resolve())
        self._setup_exit_traps()

    def unregister_active_worktree(self, worktree_path: Path | str) -> None:
        self.active_worktrees.pop(str(Path(worktree_path).resolve()), None)

    def get_repo_slug(self, repo_path: Path | str) -> str:
        """Derives owner/repo slug from git remote or folder name."""
        path = Path(repo_path).resolve()
        try:
            res = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=path,
                capture_output=True,
                text=True,
                check=False,
            )
            url = res.stdout.strip()
            if url:
                # Handle git@github.com:owner/repo.git or https://github.com/owner/repo.git
                cleaned = url.removesuffix(".git")
                if ":" in cleaned:
                    parts = cleaned.split(":")[-1].split("/")
                    if len(parts) >= 2:
                        return f"{parts[-2]}/{parts[-1]}"
                elif "/" in cleaned:
                    parts = cleaned.split("/")
                    if len(parts) >= 2:
                        return f"{parts[-2]}/{parts[-1]}"
        except Exception:
            pass
        return path.name

    def get_worktree_path(self, repo_slug: str, issue_id: str | int) -> Path:
        """Constructs target staging path ~/.factory/worktrees/<repo-slug>/<issue-id>."""
        clean_slug = repo_slug.strip().strip("/")
        return self.base_dir / clean_slug / str(issue_id)

    def create_worktree(
        self,
        repo_path: Path | str,
        branch: str,
        issue_id: str | int,
        repo_slug: Optional[str] = None,
    ) -> Path:
        """Creates an isolated worktree for the given repository and issue."""
        repo_p = Path(repo_path).resolve()
        slug = repo_slug or self.get_repo_slug(repo_p)
        target_path = self.get_worktree_path(slug, issue_id)

        if self.dry_run:
            logger.info("[dry-run] Would create worktree at %s (branch: %s)", target_path, branch)
            return target_path

        # If already exists and valid, return it; otherwise prune stale worktree
        if target_path.exists():
            if (target_path / ".git").exists():
                logger.info("Reusing existing worktree at %s", target_path)
                self.register_active_worktree(target_path, repo_p)
                return target_path
            else:
                shutil.rmtree(target_path, ignore_errors=True)

        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if branch exists
        branch_check = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            cwd=repo_p,
            capture_output=True,
        )
        has_branch = branch_check.returncode == 0

        cmd = ["git", "worktree", "add"]
        if has_branch:
            cmd.extend([str(target_path), branch])
        else:
            cmd.extend(["-b", branch, str(target_path)])

        res = subprocess.run(cmd, cwd=repo_p, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"git worktree add failed: {res.stderr.strip()}")

        self.register_active_worktree(target_path, repo_p)
        logger.info("Successfully created worktree at %s on branch %s", target_path, branch)
        return target_path

    def cleanup_worktree(
        self,
        worktree_path: Path | str,
        repo_path: Path | str,
        force: bool = False,
    ) -> None:
        """Removes worktree cleanly and prunes git metadata."""
        wt_p = Path(worktree_path).resolve()
        repo_p = Path(repo_path).resolve()

        if self.dry_run:
            logger.info("[dry-run] Would cleanup worktree at %s", wt_p)
            self.unregister_active_worktree(wt_p)
            return

        if wt_p.exists():
            cmd = ["git", "worktree", "remove", str(wt_p)]
            if force:
                cmd.append("--force")

            res = subprocess.run(cmd, cwd=repo_p, capture_output=True, text=True)
            if res.returncode != 0 and wt_p.exists():
                shutil.rmtree(wt_p, ignore_errors=True)

        subprocess.run(["git", "worktree", "prune"], cwd=repo_p, capture_output=True)
        self.unregister_active_worktree(wt_p)
        logger.info("Cleaned up worktree at %s", wt_p)


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="External Core Factory Runner Engine")
    parser.add_argument("--repo", required=True, help="Target project repository path or slug")
    parser.add_argument("--issue", required=True, help="Target issue number or identifier")
    parser.add_argument("--branch", required=True, help="Feature branch to checkout or create")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying files")
    parser.add_argument("--base-dir", default=None, help="Custom staging directory for worktrees")
    return parser.parse_args(args)


def run_cli(args: Optional[List[str]] = None) -> int:
    parsed = parse_args(args)
    manager = WorktreeManager(base_dir=parsed.base_dir, dry_run=parsed.dry_run)
    try:
        wt_path = manager.create_worktree(
            repo_path=parsed.repo,
            branch=parsed.branch,
            issue_id=parsed.issue,
        )
        print(f"Worktree ready at: {wt_path}")
        return 0
    except Exception as e:
        logger.error("Runner execution failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(run_cli())
