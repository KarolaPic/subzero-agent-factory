#!/usr/bin/env python3
"""Classify pull request diffs into the three-tier risk model:
'low-risk', 'normal', or 'high-risk'.

Risk Classification Model (#28 / #56):
1. Low-Risk ('low-risk'):
   - Docs only (e.g. *.md, docs/*, *.txt) with zero high-risk paths.
   - Tests only (e.g. tests/*) with zero high-risk paths.
   - Small code fix under 50 changed lines (additions + deletions < 50) with zero high-risk paths.
   - Auto-merge eligible upon green CI and passed independent verification/audit.

2. Normal Risk ('normal'):
   - Standard code changes (additions + deletions >= 50 lines) with zero high-risk paths.
   - Routes to the reviewer agent ('review-pr').
   - Auto-merge eligible upon green CI AND formal reviewer approval.

3. High-Risk ('high-risk' / 'needs-approval'):
   - Touching any protected or high-risk path/change type:
     * Auth / secrets (.env*, auth/*, secrets/*, token/credential management)
     * CI / workflows (.github/workflows/*)
     * Branch rules / rulesets (.github/rulesets/*, ruleset configs)
     * Dependencies or package manifests (package.json, requirements.txt, pyproject.toml, go.mod, Cargo.toml, etc.)
     * Model configs (models.yml, models.allowed.yml)
     * Database migrations / deletions (migrations/*, *.sql)
     * Deployment configurations (deploy/*, Dockerfile, docker-compose.*)
     * Factory core config (.factory/*)
     * Skill self-evolution & control plane (.agents/skills/*, AGENTS.md per ADR 0001)
   - NEVER auto-merges autonomously; halts and requests explicit human review from César.
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

HIGH_RISK_EXACT_FILES = {
    # Models & model routing
    "models.yml",
    "models.allowed.yml",
    "AGENTS.md",
    # Package manifests and lockfiles
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
    # Environment & secrets
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.staging",
    ".env.test",
    # Deployment & containerization
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}

HIGH_RISK_PREFIXES = (
    ".github/workflows/",
    ".github/rulesets/",
    ".factory/",
    ".agents/skills/",
    "scripts/",
    "migrations/",
    "migration/",
    "auth/",
    "secrets/",
    "deploy/",
)

PROTECTED_EXACT_FILES = HIGH_RISK_EXACT_FILES
PROTECTED_PREFIXES = HIGH_RISK_PREFIXES


def get_high_risk_violation(path_str: str) -> Optional[str]:
    norm = path_str.replace(chr(92), '/').strip()
    basename = Path(norm).name

    # 1. Exact match checks
    if norm in HIGH_RISK_EXACT_FILES or basename in HIGH_RISK_EXACT_FILES:
        if norm.startswith('.github/workflows/') or 'workflow' in norm:
            return f'Touches protected workflow path: {norm}'
        if norm.startswith('models') or 'model' in norm:
            return f'Touches protected model configuration: {norm}'
        if norm == 'AGENTS.md' or norm.startswith('.agents/skills/'):
            return f'Touches protected skill evolution / control plane path: {norm} (ADR 0001)'
        if norm.startswith('.env') or 'env' in basename:
            return f'Touches protected auth/secrets configuration: {norm}'
        if 'docker' in norm.lower() or 'deploy' in norm.lower():
            return f'Touches protected deployment configuration: {norm}'
        return f'Touches protected dependency or config file: {norm}'

    # 2. Prefix checks
    for prefix in HIGH_RISK_PREFIXES:
        if norm.startswith(prefix):
            if prefix.startswith('.github/workflows'):
                return f'Touches protected workflow path: {norm}'
            if prefix.startswith('.github/rulesets'):
                return f'Touches protected branch ruleset configuration: {norm}'
            if prefix.startswith('.agents/skills'):
                return f'Touches protected skill evolution path: {norm} (ADR 0001)'
            if prefix.startswith('.factory'):
                return f'Touches protected factory config path: {norm}'
            if prefix.startswith('scripts'):
                return f'Touches protected script automation path: {norm}'
            if prefix.startswith('migrations') or prefix.startswith('migration'):
                return f'Touches protected database migrations path: {norm}'
            if prefix.startswith('auth') or prefix.startswith('secrets'):
                return f'Touches protected auth/secrets path: {norm}'
            if prefix.startswith('deploy'):
                return f'Touches protected deployment configuration: {norm}'
            return f'Touches protected high-risk path: {norm}'

    # 3. Pattern checks for non-test files
    is_test = False
    for pat in TEST_PATTERNS:
        if re.search(pat, norm):
            is_test = True
            break

    # Branch rulesets anywhere
    if '.github/rulesets' in norm or re.search(r'(^|/)rulesets?/', norm):
        return f'Touches protected branch ruleset configuration: {norm}'

    # Database migrations (.sql files or migration directories)
    if not is_test and (re.search(r'(^|/)migrations?/', norm) or norm.endswith('.sql')):
        return f'Touches protected database migration: {norm}'

    # Auth and secrets paths
    if not is_test and (re.search(r'(^|/)(auth|secrets)/', norm) or re.search(r'(^|/)\.env(\..+)?$', norm)):
        return f'Touches protected auth/secrets path: {norm}'

    # Deploy scripts and configurations
    if not is_test and (
        re.search(r'(^|/)deploy/', norm)
        or re.search(r'.*deploy.*\.sh$', norm)
        or re.search(r'(^|/)Dockerfile', norm)
    ):
        return f'Touches protected deployment configuration: {norm}'

    return None


get_protected_path_violation = get_high_risk_violation


def is_doc_path(path_str: str) -> bool:
    norm = path_str.replace(chr(92), '/').strip()
    if get_high_risk_violation(norm) is not None:
        return False
    if norm.startswith('docs/'):
        return True
    path = Path(norm)
    return path.suffix.lower() in DOC_EXTENSIONS


def is_test_path(path_str: str) -> bool:
    norm = path_str.replace(chr(92), '/').strip()
    if get_high_risk_violation(norm) is not None:
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
        stats.append({'path': path, 'additions': additions, 'deletions': deletions})
    return stats


def classify_file_stats(stats: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not stats:
        return {
            'classification': 'low-risk',
            'risk_tier': 'low-risk',
            'is_low_risk': True,
            'is_normal': False,
            'is_high_risk': False,
            'requires_cesar': False,
            'routes_to': 'auto-merge',
            'total_changed_lines': 0,
            'reasons': ['Empty diff - no files changed'],
            'files_count': 0,
        }

    total_changed_lines = sum(s['additions'] + s['deletions'] for s in stats)

    # Invariant: Any high-risk path immediately requires César approval
    violations = []
    for s in stats:
        v = get_high_risk_violation(s['path'])
        if v:
            violations.append(v)

    if violations:
        return {
            'classification': 'high-risk',
            'risk_tier': 'high-risk',
            'is_low_risk': False,
            'is_normal': False,
            'is_high_risk': True,
            'requires_cesar': True,
            'routes_to': 'cesar',
            'total_changed_lines': total_changed_lines,
            'reasons': violations,
            'files_count': len(stats),
        }

    all_docs = all(is_doc_path(s['path']) for s in stats)
    all_tests = all(is_test_path(s['path']) for s in stats)

    # 1. Docs only rule (low-risk)
    if all_docs:
        return {
            'classification': 'low-risk',
            'risk_tier': 'low-risk',
            'is_low_risk': True,
            'is_normal': False,
            'is_high_risk': False,
            'requires_cesar': False,
            'routes_to': 'auto-merge',
            'total_changed_lines': total_changed_lines,
            'reasons': ['Documentation-only changes across all files'],
            'files_count': len(stats),
        }

    # 2. Tests only rule (low-risk)
    if all_tests:
        return {
            'classification': 'low-risk',
            'risk_tier': 'low-risk',
            'is_low_risk': True,
            'is_normal': False,
            'is_high_risk': False,
            'requires_cesar': False,
            'routes_to': 'auto-merge',
            'total_changed_lines': total_changed_lines,
            'reasons': ['Test-only changes across all files'],
            'files_count': len(stats),
        }

    # 3. Small fix under 50 changed lines with no high-risk paths (low-risk)
    if total_changed_lines < 50:
        return {
            'classification': 'low-risk',
            'risk_tier': 'low-risk',
            'is_low_risk': True,
            'is_normal': False,
            'is_high_risk': False,
            'requires_cesar': False,
            'routes_to': 'auto-merge',
            'total_changed_lines': total_changed_lines,
            'reasons': [
                f'Small code fix: {total_changed_lines} changed lines (< 50 lines) with no high-risk paths'
            ],
            'files_count': len(stats),
        }

    # 4. Normal code fix (>= 50 lines, no high-risk paths) -> routes to reviewer agent
    return {
        'classification': 'normal',
        'risk_tier': 'normal',
        'is_low_risk': False,
        'is_normal': True,
        'is_high_risk': False,
        'requires_cesar': False,
        'routes_to': 'reviewer-agent',
        'total_changed_lines': total_changed_lines,
        'reasons': [
            f'Code diff has {total_changed_lines} changed lines (>= 50 lines) with no high-risk paths; routes to reviewer agent'
        ],
        'files_count': len(stats),
    }


def can_auto_merge(
    stats: List[Dict[str, Any]],
    ci_passed: bool = True,
    audit_passed: bool = True,
    reviewer_approved: bool = False,
) -> tuple[bool, str]:
    """Determine if a PR can autonomously auto-merge or requires manual human approval."""
    classification_res = classify_file_stats(stats)
    if classification_res['is_high_risk']:
        reasons_summary = '; '.join(classification_res.get('reasons', []))
        return False, f"PR classified as 'high-risk' ({reasons_summary}) — waiting for César"

    if not ci_passed:
        return False, 'CI check not green — auto-merge blocked'

    if classification_res['is_low_risk']:
        if not (audit_passed or reviewer_approved):
            return False, 'PR is low-risk and CI green, but audit/reviewer approval missing — auto-merge blocked'
        return True, 'Eligible for auto-merge: low-risk, CI green, and audit/review passed'

    if classification_res['is_normal']:
        if not reviewer_approved:
            return False, 'PR is normal-risk: awaiting reviewer agent approval — auto-merge blocked'
        return True, 'Eligible for auto-merge: normal-risk, CI green, and reviewer agent approved'

    return False, 'Auto-merge blocked'


def apply_pr_label(pr_number: int, classification: str) -> None:
    """Apply the risk label to a GitHub pull request via ."""
    valid_labels = {'low-risk', 'normal', 'high-risk', 'needs-approval'}
    label_to_apply = 'high-risk' if classification in {'high-risk', 'needs-approval'} else classification
    if label_to_apply not in valid_labels:
        raise ValueError(f'Invalid classification label: {classification}. Expected {valid_labels}')

    labels_to_remove = [l for l in ['low-risk', 'normal', 'high-risk', 'needs-approval'] if l != label_to_apply]
    cmd = ['gh', 'pr', 'edit', str(pr_number), '--add-label', label_to_apply]
    for r in labels_to_remove:
        cmd.extend(['--remove-label', r])

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        cmd_fallback = ['gh', 'pr', 'edit', str(pr_number), '--add-label', label_to_apply]
        subprocess.run(cmd_fallback, check=True, capture_output=True, text=True)


def get_git_diff_numstat(base_ref: Optional[str] = None, head_ref: str = 'HEAD') -> str:
    candidates = []
    if base_ref:
        candidates.append(['git', 'diff', '--numstat', f'{base_ref}...{head_ref}'])
        candidates.append(['git', 'diff', '--numstat', base_ref, head_ref])
    else:
        for default_base in ['origin/main', 'main', 'HEAD~1']:
            candidates.append(['git', 'diff', '--numstat', f'{default_base}...{head_ref}'])
            candidates.append(['git', 'diff', '--numstat', default_base, head_ref])
        candidates.append(['git', 'diff', '--numstat', 'HEAD'])

    for cmd in candidates:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return res.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    return ''


def main() -> int:
    parser = argparse.ArgumentParser(description='Classify PR risk into low-risk, normal, or high-risk.')
    parser.add_argument('--stdin', action='store_true', help='Read git diff --numstat from standard input')
    parser.add_argument('--base', type=str, default=None, help='Base git ref for diff comparison (e.g. origin/main)')
    parser.add_argument('--head', type=str, default='HEAD', help='Head git ref for diff comparison')
    parser.add_argument('--label', action='store_true', help='Output only the label string (low-risk, normal, or high-risk)')
    parser.add_argument('--apply-pr', type=int, default=None, help='PR number to apply the resulting risk label to via gh')

    args = parser.parse_args()

    if args.stdin:
        numstat_text = sys.stdin.read()
    else:
        numstat_text = get_git_diff_numstat(args.base, args.head)

    stats = parse_numstat(numstat_text)
    result = classify_file_stats(stats)

    if args.apply_pr:
        apply_pr_label(args.apply_pr, result['classification'])

    if args.label:
        print(result['classification'])
    else:
        print(json.dumps(result, indent=2))

    return 0


if __name__ == '__main__':
    sys.exit(main())
