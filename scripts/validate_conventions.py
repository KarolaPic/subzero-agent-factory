#!/usr/bin/env python3
"""
Validator for Conventional Branch and Conventional Commit standards.

Specifications:
- Conventional Branch (https://conventionalbranch.org/):
  Pattern: <type>/<description>
  Trunk branches: main, master, develop
  Permitted types: feat, feature, fix, bugfix, hotfix, release, chore, docs, refactor, test, style, perf
  Description rules: lowercase alphanumerics (a-z, 0-9), hyphens (-), and dots (.).
  No consecutive hyphens (--) or dots (..), no leading or trailing hyphens or dots.
  Examples: feat/94-conventional-branch, fix/12-webhook-leak, chore/deps-update

- Conventional Commits (https://www.conventionalcommits.org/):
  Pattern: <type>(<scope>): <summary>
  Types: feat, fix, chore, docs, refactor, test, style, perf
"""

import argparse
import json
import re
import subprocess
import sys
from typing import Dict, Any, Tuple

# Conventional Branch types per conventionalbranch.org specification
BRANCH_TYPES = {
    "feat", "feature",
    "fix", "bugfix",
    "hotfix",
    "release",
    "chore",
    "docs",
    "refactor",
    "test",
    "style",
    "perf",
    "ai",
}

TRUNK_BRANCHES = {"main", "master", "develop"}

COMMIT_TYPES = {
    "feat", "fix", "chore", "docs", "refactor", "test", "style", "perf", "ci", "build", "revert"
}


def validate_branch_name(branch: str) -> Tuple[bool, str]:
    """Validate a git branch name against the Conventional Branch specification."""
    b = branch.strip()
    if not b:
        return False, "Branch name cannot be empty."

    if b in TRUNK_BRANCHES:
        return True, f"Trunk branch '{b}' is valid."

    if "/" not in b:
        return False, (
            f"Branch '{b}' lacks a type prefix. "
            f"Conventional Branch format requires '<type>/<description>' "
            f"(e.g. 'feat/94-add-feature' or 'fix/12-bug-fix')."
        )

    parts = b.split("/", 1)
    prefix, description = parts[0], parts[1]

    if prefix not in BRANCH_TYPES:
        allowed = ", ".join(sorted(BRANCH_TYPES))
        return False, (
            f"Invalid branch type '{prefix}'. Must be one of: {allowed}."
        )

    if not description:
        return False, f"Branch description in '{b}' cannot be empty."

    # Rule: Lowercase letters (a-z), numbers (0-9), hyphens (-), and dots (.)
    if not re.match(r"^[a-z0-9\.\-]+$", description):
        return False, (
            f"Invalid characters in description '{description}'. "
            "Conventional Branch only allows lowercase alphanumeric characters (a-z, 0-9), hyphens (-), and dots (.)."
        )

    # Rule: No leading or trailing hyphens or dots
    if description.startswith("-") or description.startswith("."):
        return False, f"Branch description '{description}' cannot start with a hyphen or dot."

    if description.endswith("-") or description.endswith("."):
        return False, f"Branch description '{description}' cannot end with a hyphen or dot."

    # Rule: No consecutive hyphens or dots
    if "--" in description:
        return False, f"Branch description '{description}' cannot contain consecutive hyphens ('--')."

    if ".." in description:
        return False, f"Branch description '{description}' cannot contain consecutive dots ('..')."

    if "-." in description or ".-" in description:
        return False, f"Branch description '{description}' cannot contain mixed consecutive separators ('-.' or '.-')."

    return True, f"Branch '{b}' conforms to Conventional Branch."


def validate_commit_message(message: str) -> Tuple[bool, str]:
    """Validate a commit subject line against Conventional Commits."""
    first_line = message.strip().split("\n")[0].strip()
    if not first_line:
        return False, "Commit message cannot be empty."

    pattern = r"^([a-z]+)(?:\(([a-z0-9_\-\.\/]+)\))?(!)?:\s+(.+)$"
    match = re.match(pattern, first_line)
    if not match:
        return False, (
            f"Commit subject '{first_line}' does not follow Conventional Commits format: "
            "<type>(<scope>): <description> (e.g. 'feat(run-epic): add support (#89)')."
        )

    commit_type = match.group(1)
    if commit_type not in COMMIT_TYPES:
        allowed = ", ".join(sorted(COMMIT_TYPES))
        return False, (
            f"Invalid commit type '{commit_type}'. Must be one of: {allowed}."
        )

    description = match.group(4)
    if not description or len(description.strip()) < 3:
        return False, "Commit description is too short or empty."

    return True, f"Commit subject '{first_line}' conforms to Conventional Commits."


def validate_pr_title(title: str) -> Tuple[bool, str]:
    """Validate a PR title against Conventional Commits."""
    return validate_commit_message(title)


def get_current_branch() -> str:
    """Retrieve currently checked-out git branch name."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True
        )
        return res.stdout.strip()
    except Exception:
        return ""


def main():
    parser = argparse.ArgumentParser(
        description="Validate git branch, commit message, or PR title against Conventional conventions."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Branch command
    branch_parser = subparsers.add_parser("branch", help="Validate a branch name")
    branch_parser.add_argument("name", nargs="?", help="Branch name to validate (defaults to current branch)")
    branch_parser.add_argument("--json", action="store_true", help="Output JSON result")

    # Commit command
    commit_parser = subparsers.add_parser("commit", help="Validate a commit message")
    commit_parser.add_argument("message", help="Commit message to validate")
    commit_parser.add_argument("--json", action="store_true", help="Output JSON result")

    # PR title command
    pr_parser = subparsers.add_parser("pr-title", help="Validate a PR title")
    pr_parser.add_argument("title", help="PR title to validate")
    pr_parser.add_argument("--json", action="store_true", help="Output JSON result")

    args = parser.parse_args()

    if args.command == "branch":
        name = args.name or get_current_branch()
        valid, msg = validate_branch_name(name)
        if args.json:
            print(json.dumps({"type": "branch", "name": name, "valid": valid, "message": msg}, indent=2))
        else:
            print(msg)
        sys.exit(0 if valid else 1)

    elif args.command == "commit":
        valid, msg = validate_commit_message(args.message)
        if args.json:
            print(json.dumps({"type": "commit", "message": args.message, "valid": valid, "details": msg}, indent=2))
        else:
            print(msg)
        sys.exit(0 if valid else 1)

    elif args.command == "pr-title":
        valid, msg = validate_pr_title(args.title)
        if args.json:
            print(json.dumps({"type": "pr_title", "title": args.title, "valid": valid, "details": msg}, indent=2))
        else:
            print(msg)
        sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()
