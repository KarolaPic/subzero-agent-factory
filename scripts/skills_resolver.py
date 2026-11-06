#!/usr/bin/env python3
"""Layered Skills Resolver and Worktree Overlay Engine.

Dynamically overlays Global Core Skills from the factory repository into the
target worktree's .agents/skills/ directory. Preserves project-local skills on
name collision and applies .factory.yml exclusion filters.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("skills_resolver")

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_GLOBAL_SKILLS_DIR = ROOT_DIR / ".agents" / "skills"


def resolve_skills_overlay(
    target_worktree: Path | str,
    global_skills_dir: Optional[Path | str] = None,
    exclude_skills: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Overlays global core skills into worktree .agents/skills via symlinks.

    Returns a summary dictionary: {skill_name: resolution_status}
    where resolution_status is one of: 'global_symlink', 'local_preserved', 'excluded'.
    """
    g_dir = Path(global_skills_dir or DEFAULT_GLOBAL_SKILLS_DIR).resolve()
    wt_dir = Path(target_worktree).resolve()
    target_skills_dir = wt_dir / ".agents" / "skills"

    target_skills_dir.mkdir(parents=True, exist_ok=True)
    excluded_set = set(exclude_skills or [])
    summary: Dict[str, str] = {}

    if not g_dir.is_dir():
        logger.warning("Global skills directory not found at %s", g_dir)
        return summary

    for entry in sorted(g_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue

        skill_name = entry.name

        # 1. Exclusion filter
        if skill_name in excluded_set:
            summary[skill_name] = "excluded"
            continue

        target_skill_path = target_skills_dir / skill_name

        # 2. Local precedence collision check
        if target_skill_path.exists() or target_skill_path.is_symlink():
            if not target_skill_path.is_symlink():
                # Real local directory or file -> preserve local precedence
                summary[skill_name] = "local_preserved"
                continue
            else:
                # Existing symlink -> remove and re-link cleanly
                try:
                    target_skill_path.unlink()
                except OSError:
                    pass

        # 3. Create symlink from global skills to worktree
        try:
            target_skill_path.symlink_to(entry.resolve(), target_is_directory=True)
            summary[skill_name] = "global_symlink"
        except Exception as e:
            logger.error("Failed to symlink skill %s: %s", skill_name, e)
            summary[skill_name] = f"error: {e}"

    return summary


def clean_skills_overlay(target_worktree: Path | str) -> int:
    """Removes all symlinked global skills from worktree, preserving project-local skills."""
    wt_dir = Path(target_worktree).resolve()
    target_skills_dir = wt_dir / ".agents" / "skills"

    if not target_skills_dir.is_dir():
        return 0

    removed = 0
    for entry in target_skills_dir.iterdir():
        if entry.is_symlink():
            try:
                entry.unlink()
                removed += 1
            except OSError as e:
                logger.error("Failed to remove symlink %s: %s", entry, e)

    return removed


def main(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="External Factory Layered Skills Resolver")
    parser.add_argument("--worktree", required=True, help="Target project worktree directory")
    parser.add_argument("--global-skills", default=None, help="Global core skills directory")
    parser.add_argument("--exclude", nargs="*", default=[], help="Skills to exclude")
    parser.add_argument("--clean", action="store_true", help="Remove all overlay symlinks")

    parsed = parser.parse_args(args)

    if parsed.clean:
        count = clean_skills_overlay(parsed.worktree)
        print(f"Removed {count} overlay symlinks from {parsed.worktree}")
        return 0

    summary = resolve_skills_overlay(
        target_worktree=parsed.worktree,
        global_skills_dir=parsed.global_skills,
        exclude_skills=parsed.exclude,
    )
    for name, status in sorted(summary.items()):
        print(f"  {name}: {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
