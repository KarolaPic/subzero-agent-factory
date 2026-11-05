#!/usr/bin/env python3
"""Classify pull request diffs as 'low-risk' or 'needs-approval'.

Low-Risk Rule:
1. Docs only (e.g. *.md, docs/*, *.txt) -> low-risk (any size), provided no protected paths are touched.
2. Tests only (e.g. tests/*) -> low-risk (any size), provided no protected paths are touched.
3. Small fix under 50 changed lines (additions + deletions < 50) AND
   touches NO protected/high-risk paths:
   - Workflows (.github/workflows/*)
   - Model configs (models*.yml, models.allowed.yml)
   - Dependencies (package.json, requirements.txt, pyproject.toml, go.mod, Cargo.toml, etc.)
   - Factory core config (.factory/*)
   - Skill self-evolution & control plane (.agents/skills/*, AGENTS.md per ADR 0001)

All other PRs are classified as 'needs-approval'.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


DOC_EXTENSIONS = {".md", ".txt", ".rst", ".adoc"}
TEST_PATTERNS = [
    r"^tests/",
    r".*_test\.py$",
    r".*test_.*\.py$",
    r".*\.test\.[jt]sx?$",
    r".*\.spec\.[jt]sx?$",
]

PROTECTED_EXACT_FILES = {
    "models.yml",
    "models.allowed.yml",
    "AGENTS.md",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "Pipfile",
    "Pipfile.lock",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
}

PROTECTED_PREFIXES = (
    ".github/workflows/",
    ".factory/",
    ".agents/skills/",
)


def get_protected_path_violation(path_str: str) -> Optional[str]:
    norm = path_str.replace("\\", "/").strip()
    basename = Path(norm).name

    if norm in PROTECTED_EXACT_FILES or basename in PROTECTED_EXACT_FILES:
        if "workflow" in norm or norm.startswith(".github/workflows/"):
            return f"Touches protected workflow path: {norm}"
        if norm.startswith("models") or "model" in norm:
            return f"Touches protected model configuration: {norm}"
        if norm == "AGENTS.md" or norm.startswith(".agents/skills/"):
            return f"Touches protected skill evolution / control plane path: {norm} (ADR 0001)"
        return f"Touches protected dependency or config file: {norm}"

    for prefix in PROTECTED_PREFIXES:
        if norm.startswith(prefix):
            if prefix.startswith(".github/workflows"):
                return f"Touches protected workflow path: {norm}"
            if prefix.startswith(".agents/skills"):
                return f"Touches protected skill evolution path: {norm} (ADR 0001)"
            return f"Touches protected factory config path: {norm}"

    return None


def is_doc_path(path_str: str) -> bool:
    norm = path_str.replace("\\", "/").strip()
    if get_protected_path_violation(norm) is not None:
        return False
    if norm.startswith("docs/"):
        return True
    path = Path(norm)
    return path.suffix.lower() in DOC_EXTENSIONS


def is_test_path(path_str: str) -> bool:
    norm = path_str.replace("\\", "/").strip()
    if get_protected_path_violation(norm) is not None:
        return False
    for pattern in TEST_PATTERNS:
        if re.search(pattern, norm):
            return True
    return False


def parse_numstat(text: str) -> List[Dict[str, Any]]:
    stats = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        add_str, del_str, path = parts[0], parts[1], parts[2]
        additions = int(add_str) if add_str.isdigit() else 0
        deletions = int(del_str) if del_str.isdigit() else 0
        stats.append({"path": path, "additions": additions, "deletions": deletions})
    return stats


def classify_file_stats(stats: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not stats:
        return {
            "classification": "low-risk",
            "is_low_risk": True,
            "total_changed_lines": 0,
            "reasons": ["Empty diff - no files changed"],
            "files_count": 0,
        }

    total_changed_lines = sum(s["additions"] + s["deletions"] for s in stats)

    # Invariant: Any protected/high-risk path immediately requires approval
    violations = []
    for s in stats:
        v = get_protected_path_violation(s["path"])
        if v:
            violations.append(v)

    if violations:
        return {
            "classification": "needs-approval",
            "is_low_risk": False,
            "total_changed_lines": total_changed_lines,
            "reasons": violations,
            "files_count": len(stats),
        }

    all_docs = all(is_doc_path(s["path"]) for s in stats)
    all_tests = all(is_test_path(s["path"]) for s in stats)

    # 1. Docs only rule (unrestricted lines when no protected paths touched)
    if all_docs:
        return {
            "classification": "low-risk",
            "is_low_risk": True,
            "total_changed_lines": total_changed_lines,
            "reasons": ["Documentation-only changes across all files"],
            "files_count": len(stats),
        }

    # 2. Tests only rule (unrestricted lines when no protected paths touched)
    if all_tests:
        return {
            "classification": "low-risk",
            "is_low_risk": True,
            "total_changed_lines": total_changed_lines,
            "reasons": ["Test-only changes across all files"],
            "files_count": len(stats),
        }

    # 3. Small fix under 50 changed lines with no protected paths
    if total_changed_lines < 50:
        return {
            "classification": "low-risk",
            "is_low_risk": True,
            "total_changed_lines": total_changed_lines,
            "reasons": [
                f"Small code fix: {total_changed_lines} changed lines (< 50 lines) with no protected paths"
            ],
            "files_count": len(stats),
        }

    # Exceeds 50 lines
    return {
        "classification": "needs-approval",
        "is_low_risk": False,
        "total_changed_lines": total_changed_lines,
        "reasons": [
            f"Code diff has {total_changed_lines} changed lines (exceeds the 50-line low-risk threshold)"
        ],
        "files_count": len(stats),
    }


def get_git_diff_numstat(base_ref: Optional[str] = None, head_ref: str = "HEAD") -> str:
    candidates = []
    if base_ref:
        candidates.append(["git", "diff", "--numstat", f"{base_ref}...{head_ref}"])
        candidates.append(["git", "diff", "--numstat", base_ref, head_ref])
    else:
        for default_base in ["origin/main", "main", "HEAD~1"]:
            candidates.append(["git", "diff", "--numstat", f"{default_base}...{head_ref}"])
            candidates.append(["git", "diff", "--numstat", default_base, head_ref])
        candidates.append(["git", "diff", "--numstat", "HEAD"])

    for cmd in candidates:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return res.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify PR risk as low-risk or needs-approval.")
    parser.add_argument("--stdin", action="store_true", help="Read git diff --numstat from standard input")
    parser.add_argument("--base", type=str, default=None, help="Base git ref for diff comparison (e.g. origin/main)")
    parser.add_argument("--head", type=str, default="HEAD", help="Head git ref for diff comparison")
    parser.add_argument("--label", action="store_true", help="Output only the label string (low-risk or needs-approval)")

    args = parser.parse_args()

    if args.stdin:
        numstat_text = sys.stdin.read()
    else:
        numstat_text = get_git_diff_numstat(args.base, args.head)

    stats = parse_numstat(numstat_text)
    result = classify_file_stats(stats)

    if args.label:
        print(result["classification"])
    else:
        print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
