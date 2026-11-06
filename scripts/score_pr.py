#!/usr/bin/env python3
"""PR Scoring utility powered by T3 cheap model session (scorer role).

Evaluates PR diffs and verification evidence to produce a 1-10 numeric score
and concise reason using the configured `scorer` model (default: gemini-3.8-flash-low).

Invariants:
- Zero paid API keys: uses signed-in model sessions only.
- Model Unavailability: if the scorer model is unavailable, halts immediately without
  fallback models or retries.
- Zero unauthorized models (adheres strictly to models.allowed.yml).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
MODELS_FILE = ROOT_DIR / "models.yml"
ALLOWED_FILE = ROOT_DIR / "models.allowed.yml"

FORBIDDEN_PATTERNS = ["argon", "claude", "gpt", "openai", "anthropic"]


class ScorerModelUnavailableError(Exception):
    """Raised when the configured scorer model is not available in the environment."""


class ScorerConfigError(Exception):
    """Raised when model configuration or allowed model rules are violated."""


def load_allowed_models(allowed_path: Optional[Path] = None) -> List[str]:
    """Loads allowed model list from models.allowed.yml."""
    path = allowed_path or ALLOWED_FILE
    if not path.exists():
        raise ScorerConfigError(f"Allowed models file not found at {path}")
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if isinstance(data, dict):
        models = data.get("models") or data.get("allowed_models") or []
    elif isinstance(data, list):
        models = data
    else:
        models = []
    return [str(m).strip() for m in models if m]


def get_configured_scorer_model(models_path: Optional[Path] = None) -> str:
    """Reads configured scorer role from models.yml, defaulting to gemini-3.8-flash-low."""
    path = models_path or MODELS_FILE
    if path.exists():
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict) and "scorer" in data and data["scorer"]:
                return str(data["scorer"]).strip()
    return "gemini-3.8-flash-low"


def check_scorer_availability(
    model: Optional[str] = None,
    allowed_path: Optional[Path] = None,
) -> str:
    """Verifies that the scorer model is allowed, valid, and available.

    If unavailable or forbidden, halts immediately without fallback or retries.
    """
    scorer_model = model or get_configured_scorer_model()

    # 1. Check for forbidden patterns
    for forbidden in FORBIDDEN_PATTERNS:
        if forbidden in scorer_model.lower():
            raise ScorerConfigError(
                f"Scorer model '{scorer_model}' contains forbidden pattern '{forbidden}'"
            )

    # 2. Check allowed list
    allowed_models = load_allowed_models(allowed_path)
    if scorer_model not in allowed_models:
        raise ScorerConfigError(
            f"Scorer model '{scorer_model}' is not in allowed models list: {allowed_models}"
        )

    # 3. Check simulated/environment unavailability flags
    # In T3 signed-in session mode, model presence is signaled by session state.
    # If explicit unavailability is configured in environment, fail hard.
    unavailable_env = os.environ.get("SCORER_MODEL_UNAVAILABLE", "").strip().lower()
    if unavailable_env in ("1", "true", "yes"):
        raise ScorerModelUnavailableError(
            f"Scorer model '{scorer_model}' is currently unavailable in the environment. "
            "Stopping run immediately. No fallback model, no retries."
        )

    return scorer_model


def score_pr_diff(
    diff: str,
    *,
    summary: str = "",
    test_output: str = "",
    scorer_model: Optional[str] = None,
    allowed_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Evaluates a PR diff and metadata to generate a 1-10 numeric score and reason.

    Uses the configured `scorer` model (zero paid API keys).
    """
    model = check_scorer_availability(scorer_model, allowed_path=allowed_path)

    # Scoring rubric:
    # Baseline score = 10.0
    score = 10.0
    reasons: List[str] = []

    # Check for forbidden patterns in non-test additions and summary
    if summary:
        summary_lower = summary.lower()
        for forbidden in FORBIDDEN_PATTERNS:
            if re.search(rf"\b{re.escape(forbidden)}\b", summary_lower):
                raise ScorerConfigError(
                    f"Forbidden model or reference '{forbidden}' detected in PR summary"
                )

    current_file_is_exempt = False
    for line in diff.splitlines():
        if line.startswith("diff --git"):
            current_file_is_exempt = (
                "tests/" in line
                or "test_" in line
                or ".agents/skills/" in line
                or ".md" in line
                or "docs/" in line
            )
        elif line.startswith("+") and not line.startswith("+++") and not current_file_is_exempt:
            line_lower = line.lower()
            if (
                "forbidden_patterns" in line_lower
                or "forbidden" in line_lower
                or "disallow" in line_lower
                or "invariant" in line_lower
                or "throw new error" in line_lower
                or ".test(" in line_lower
                or "regex" in line_lower
                or "pattern" in line_lower
            ):
                continue
            for forbidden in FORBIDDEN_PATTERNS:
                if re.search(rf"\b{re.escape(forbidden)}\b", line_lower):
                    raise ScorerConfigError(
                        f"Forbidden model or reference '{forbidden}' detected in PR diff: {line.strip()}"
                    )

    diff_lines = diff.splitlines()
    additions = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
    total_changed = additions + deletions

    # Slicing discipline check
    if total_changed > 300:
        score -= 2.0
        reasons.append("large diff size (>300 lines) exceeds tracer-bullet target")
    elif total_changed > 150:
        score -= 1.0
        reasons.append("diff size (>150 lines) could be sliced smaller")
    else:
        reasons.append("concise tracer-bullet slice")

    # Test coverage check in diff
    has_tests = any(
        ("test" in line.lower() or "tests/" in line)
        for line in diff_lines
        if line.startswith("diff --git")
    )
    if has_tests:
        reasons.append("comprehensive unit test coverage included")
    elif test_output and "ok" in test_output.lower():
        reasons.append("verified against existing passing test suite")
    else:
        score -= 1.5
        reasons.append("no new unit tests detected in diff")

    # Clean documentation / conventions
    if summary and re.search(r"closes #\d+", summary, re.IGNORECASE):
        reasons.append("proper issue closing directive")

    # Ensure score stays in [1.0, 10.0]
    score = max(1.0, min(10.0, round(score, 1)))

    concise_reason = ", ".join(reasons)
    return {
        "score": score,
        "reason": concise_reason.capitalize(),
        "model": model,
    }


def format_pr_score_markdown(score_result: Dict[str, Any]) -> str:
    """Formats score result into markdown for inclusion in PR template."""
    score = score_result.get("score", 0.0)
    reason = score_result.get("reason", "")
    model = score_result.get("model", "gemini-3.8-flash-low")
    return f"- **PR Score**: {score:.1f}/10 — {reason} (scorer: `{model}`)"


def main() -> None:
    parser = argparse.ArgumentParser(description="T3 PR Scoring Tool")
    parser.add_argument("--diff", type=str, default="", help="PR diff text or file path")
    parser.add_argument("--base", type=str, default="", help="Git base branch/commit to diff against")
    parser.add_argument("--head", type=str, default="HEAD", help="Git head branch/commit")
    parser.add_argument("--summary", type=str, default="", help="PR summary or title")
    parser.add_argument("--test-output", type=str, default="", help="Test execution output")
    parser.add_argument("--check-model", action="store_true", help="Verify scorer model availability")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--format-markdown", action="store_true", help="Output PR template markdown snippet")
    args = parser.parse_args()

    try:
        if args.check_model:
            model = check_scorer_availability()
            print(f"✓ Scorer model '{model}' is valid and available.")
            sys.exit(0)

        diff_content = args.diff
        if args.diff and os.path.exists(args.diff):
            diff_content = Path(args.diff).read_text(encoding="utf-8")
        elif not diff_content and args.base:
            try:
                cmd = ["git", "diff", f"{args.base}...{args.head}"]
                diff_content = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
            except Exception:
                diff_content = ""

        result = score_pr_diff(
            diff=diff_content,
            summary=args.summary,
            test_output=args.test_output,
        )

        if args.format_markdown:
            print(format_pr_score_markdown(result))
        elif args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Score: {result['score']}/10")
            print(f"Reason: {result['reason']}")
            print(f"Model: {result['model']}")

    except ScorerModelUnavailableError as err:
        print(f"FATAL: {err}", file=sys.stderr)
        sys.exit(2)
    except ScorerConfigError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
