#!/usr/bin/env python3
"""Changelog updater script for Grok Bot Agent Factory.

Adheres to Keep a Changelog (https://keepachangelog.com/en/1.0.0/) and Semantic Versioning.
Automatically inserts formatted entries into CHANGELOG.md under ## [Unreleased]
with deduplication and conventional commit type mapping.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


CATEGORY_MAP = {
    "feat": "Added",
    "feature": "Added",
    "fix": "Fixed",
    "bugfix": "Fixed",
    "perf": "Changed",
    "refactor": "Changed",
    "change": "Changed",
    "deprecate": "Deprecated",
    "remove": "Removed",
    "revert": "Removed",
    "security": "Security",
    "sec": "Security",
    "docs": "Added",
    "chore": "Changed",
}

VALID_CATEGORIES = [
    "Added",
    "Changed",
    "Deprecated",
    "Removed",
    "Fixed",
    "Security",
]


def resolve_repo_root(cwd: Optional[Path] = None) -> Path:
    """Finds the root of the current Git repository."""
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd or Path.cwd(),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return Path(root)
    except Exception:
        return Path.cwd().resolve()


def get_repo_slug(cwd: Optional[Path] = None) -> str:
    """Detects github owner/repo from git remote or default."""
    try:
        remote_url = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=cwd or Path.cwd(),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        # Handle SSH (git@github.com:owner/repo.git) and HTTPS (https://github.com/owner/repo.git)
        match = re.search(r"github\.com[:/]([^/]+/[^/.]+)(?:\.git)?$", remote_url)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "cesarchavezcal/grok-bot-agent-factory"


def map_type_to_category(change_type: str) -> str:
    """Maps conventional commit type to Keep a Changelog section."""
    clean_type = change_type.strip().lower()
    return CATEGORY_MAP.get(clean_type, "Changed")


def format_entry(
    summary: str,
    repo_slug: str,
    issue: Optional[int | str] = None,
    pr: Optional[int | str] = None,
) -> str:
    """Formats a single bullet item with issue/PR links."""
    summary_clean = summary.strip().rstrip(".")
    # Capitalize first letter if not already
    if summary_clean and summary_clean[0].islower():
        summary_clean = summary_clean[0].upper() + summary_clean[1:]

    links = []
    if issue:
        issue_num = str(issue).lstrip("#")
        links.append(f"[#{issue_num}](https://github.com/{repo_slug}/issues/{issue_num})")
    if pr:
        pr_num = str(pr).lstrip("#")
        links.append(f"[#{pr_num}](https://github.com/{repo_slug}/pull/{pr_num})")

    if links:
        links_str = ", ".join(links)
        return f"- {summary_clean} ({links_str})."
    return f"- {summary_clean}."


def update_changelog_content(
    content: str,
    entry: str,
    category: str,
    pr: Optional[int | str] = None,
    issue: Optional[int | str] = None,
) -> Tuple[str, bool]:
    """Updates the changelog string with the new entry under ## [Unreleased] -> ### Category.
    
    Returns (new_content, modified_flag).
    """
    if category not in VALID_CATEGORIES:
        category = "Changed"

    # Idempotency check: if PR or entry is already present under [Unreleased]
    unreleased_match = re.search(r"##\s*\[Unreleased\](.*?)(?=\n##\s*\[|\Z)", content, re.DOTALL | re.IGNORECASE)
    if unreleased_match:
        unreleased_block = unreleased_match.group(1)
        if pr and (f"[#{pr}]" in unreleased_block or f"(#{pr})" in unreleased_block):
            return content, False
        if entry.strip() in unreleased_block:
            return content, False

    # Find the ## [Unreleased] heading
    unreleased_header_pattern = re.compile(r"(##\s*\[Unreleased\]\s*\n)", re.IGNORECASE)
    unreleased_search = unreleased_header_pattern.search(content)

    if not unreleased_search:
        # Create ## [Unreleased] header right after top metadata
        top_split = content.split("##", 1)
        if len(top_split) == 2:
            content = f"{top_split[0]}## [Unreleased]\n\n##{top_split[1]}"
        else:
            content = f"{content}\n\n## [Unreleased]\n"
        unreleased_search = unreleased_header_pattern.search(content)

    if not unreleased_search:
        raise ValueError("Could not locate or initialize ## [Unreleased] in CHANGELOG.md")

    unreleased_start = unreleased_search.end()
    # Find boundary of next version header (## [YYYY-MM-DD] or similar) or end of file
    next_header_match = re.search(r"\n##\s*\[", content[unreleased_start:])
    if next_header_match:
        unreleased_end = unreleased_start + next_header_match.start()
    else:
        unreleased_end = len(content)

    unreleased_section = content[unreleased_start:unreleased_end]

    # Look for existing category header (e.g. ### Added)
    cat_header_pattern = re.compile(rf"(###\s*{re.escape(category)}\s*\n)", re.IGNORECASE)
    cat_match = cat_header_pattern.search(unreleased_section)

    if cat_match:
        # Insert entry right under the category header
        insert_idx = unreleased_start + cat_match.end()
        new_content = content[:insert_idx] + f"{entry}\n" + content[insert_idx:]
    else:
        # Append new category header and entry to unreleased section
        addition = f"\n### {category}\n{entry}\n"
        new_content = content[:unreleased_start] + addition + unreleased_section.lstrip() + content[unreleased_end:]

    return new_content, True


def update_changelog_file(
    changelog_path: Path,
    summary: str,
    category: str,
    repo_slug: str,
    issue: Optional[int | str] = None,
    pr: Optional[int | str] = None,
) -> bool:
    """Reads changelog, applies update, and writes back if modified."""
    if not changelog_path.exists():
        initial_content = (
            "# Changelog\n\n"
            "All notable changes to the Grok Bot Agent Factory will be documented in this file.\n\n"
            "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),\n"
            "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n\n"
            "## [Unreleased]\n"
        )
        changelog_path.write_text(initial_content, encoding="utf-8")

    content = changelog_path.read_text(encoding="utf-8")
    entry = format_entry(summary, repo_slug=repo_slug, issue=issue, pr=pr)
    new_content, modified = update_changelog_content(content, entry, category, pr=pr, issue=issue)

    if modified:
        changelog_path.write_text(new_content, encoding="utf-8")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Update CHANGELOG.md under ## [Unreleased]")
    parser.add_argument("--summary", required=True, help="Description of the change")
    parser.add_argument("--type", default="feat", help="Conventional commit type (feat, fix, docs, refactor, perf, chore)")
    parser.add_argument("--category", help="Explicit Keep a Changelog category (Added, Changed, Fixed, Removed, etc.)")
    parser.add_argument("--issue", help="Associated issue number (e.g. 122 or #122)")
    parser.add_argument("--pr", help="Associated PR number (e.g. 123 or #123)")
    parser.add_argument("--repo", help="GitHub repo slug (owner/repo)")
    parser.add_argument("--changelog", help="Path to CHANGELOG.md")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing to file")

    args = parser.parse_args()

    repo_root = resolve_repo_root()
    changelog_path = Path(args.changelog) if args.changelog else (repo_root / "CHANGELOG.md")
    repo_slug = args.repo or get_repo_slug(repo_root)

    category = args.category or map_type_to_category(args.type)
    entry = format_entry(args.summary, repo_slug=repo_slug, issue=args.issue, pr=args.pr)

    if args.dry_run:
        print(f"[DRY-RUN] Would update {changelog_path} under [{category}]:")
        print(entry)
        return 0

    modified = update_changelog_file(
        changelog_path=changelog_path,
        summary=args.summary,
        category=category,
        repo_slug=repo_slug,
        issue=args.issue,
        pr=args.pr,
    )

    if modified:
        print(f"Updated {changelog_path} under '### {category}': {entry}")
    else:
        print(f"Entry already present in {changelog_path}; skipped duplicate.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
