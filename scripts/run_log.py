#!/usr/bin/env python3
"""Thread- and process-safe Run Log client for Grok Bot Agent Factory.

Provides atomic appends to .factory/runs/runs.jsonl across concurrent Git worktrees
using fcntl.flock, a dedicated lockfile, and schema validation.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional


class RunLogError(Exception):
    """Base exception for RunLog failures."""


def resolve_runs_dir(cwd: Optional[Path] = None) -> Path:
    """Resolves the canonical .factory/runs directory across Git worktrees."""
    try:
        common_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=cwd or Path.cwd(),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        common_path = (Path(cwd or Path.cwd()) / common_dir).resolve()
        repo_root = common_path.parent
    except Exception:
        repo_root = Path.cwd().resolve()

    runs_dir = repo_root / ".factory" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    return runs_dir


@contextlib.contextmanager
def runs_lock(runs_dir: Path, timeout_seconds: float = 15.0) -> Generator[None, None, None]:
    """Acquires an exclusive advisory lock on the dedicated .runs.lock file."""
    lock_file = runs_dir / ".runs.lock"
    fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o644)
    start_time = time.monotonic()

    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except (BlockingIOError, OSError):
            if time.monotonic() - start_time >= timeout_seconds:
                os.close(fd)
                raise TimeoutError(f"Timed out after {timeout_seconds}s waiting for run log lock at {lock_file}")
            time.sleep(0.05)

    try:
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _validate_iso_timestamp(ts: Optional[str], field_name: str) -> None:
    if ts is None:
        return
    if not isinstance(ts, str):
        raise RunLogError(f"Field '{field_name}' must be an ISO 8601 string or null, got {type(ts).__name__}")
    try:
        cleaned = ts.replace("Z", "+00:00")
        datetime.fromisoformat(cleaned)
    except Exception as exc:
        raise RunLogError(f"Field '{field_name}' contains invalid ISO 8601 timestamp '{ts}': {exc}") from exc


def validate_run_record(record: Dict[str, Any]) -> None:
    """Validates a single run log record against .factory/schemas/run.schema.json rules."""
    if not isinstance(record, dict):
        raise RunLogError(f"Run record must be a dict, got {type(record).__name__}")

    allowed_fields = {
        "issue",
        "pr",
        "kickoff_at",
        "pr_opened_at",
        "first_review_at",
        "merged_at",
        "human_intervened",
        "result",
        "builder",
        "auditor",
        "pr_score",
        "review_result",
        "review_rounds",
        "reviewer_model",
    }

    # Strict check: reject unexpected extra fields to avoid secret leakage
    extra_fields = set(record.keys()) - allowed_fields
    if extra_fields:
        raise RunLogError(f"Disallowed additional fields in run record: {sorted(extra_fields)}")

    # Check required fields
    missing_fields = allowed_fields - set(record.keys())
    if missing_fields:
        raise RunLogError(f"Missing required fields in run record: {sorted(missing_fields)}")

    # 1. issue: int or str
    if not isinstance(record["issue"], (int, str)) or (isinstance(record["issue"], str) and not record["issue"].strip()):
        raise RunLogError(f"Field 'issue' must be a non-empty integer or string, got {record['issue']!r}")

    # 2. pr: int, str, or None
    if record["pr"] is not None and not isinstance(record["pr"], (int, str)):
        raise RunLogError(f"Field 'pr' must be int, str, or null, got {type(record['pr']).__name__}")

    # 3. timestamps
    _validate_iso_timestamp(record["kickoff_at"], "kickoff_at")
    if record["kickoff_at"] is None:
        raise RunLogError("Field 'kickoff_at' cannot be null")

    _validate_iso_timestamp(record["pr_opened_at"], "pr_opened_at")
    _validate_iso_timestamp(record["first_review_at"], "first_review_at")
    _validate_iso_timestamp(record["merged_at"], "merged_at")

    # 4. human_intervened: bool OR { occurred: bool, count: int >= 0 }
    hi = record["human_intervened"]
    if isinstance(hi, bool):
        pass
    elif isinstance(hi, dict):
        if set(hi.keys()) != {"occurred", "count"}:
            raise RunLogError(f"Field 'human_intervened' object must have exactly ['occurred', 'count'], got {sorted(hi.keys())}")
        if not isinstance(hi["occurred"], bool):
            raise RunLogError(f"'human_intervened.occurred' must be bool, got {type(hi['occurred']).__name__}")
        if not isinstance(hi["count"], int) or hi["count"] < 0:
            raise RunLogError(f"'human_intervened.count' must be integer >= 0, got {hi['count']!r}")
    else:
        raise RunLogError(f"Field 'human_intervened' must be bool or dict, got {type(hi).__name__}")

    # 5. result: enum ["merged", "blocked", "failed"]
    if record["result"] not in ("merged", "blocked", "failed"):
        raise RunLogError(f"Field 'result' must be one of ['merged', 'blocked', 'failed'], got {record['result']!r}")

    # 6. builder & auditor: non-empty strings
    if not isinstance(record["builder"], str) or not record["builder"].strip():
        raise RunLogError(f"Field 'builder' must be a non-empty string, got {record['builder']!r}")
    if not isinstance(record["auditor"], str) or not record["auditor"].strip():
        raise RunLogError(f"Field 'auditor' must be a non-empty string, got {record['auditor']!r}")

    # 7. pr_score: float/int >= 0 or None
    score = record["pr_score"]
    if score is not None:
        if not isinstance(score, (int, float)) or isinstance(score, bool) or score < 0:
            raise RunLogError(f"Field 'pr_score' must be number >= 0 or null, got {score!r}")

    # 8. review_result: enum ["approved", "changes_requested", "skipped"] or None
    rev_res = record["review_result"]
    if rev_res is not None:
        if rev_res not in ("approved", "changes_requested", "skipped"):
            raise RunLogError(
                f"Field 'review_result' must be one of ['approved', 'changes_requested', 'skipped'] or null, got {rev_res!r}"
            )

    # 9. review_rounds: integer 1..3 (or 0/None if unreviewed or skipped)
    rounds = record["review_rounds"]
    if rounds is not None:
        if not isinstance(rounds, int) or isinstance(rounds, bool) or rounds < 0 or rounds > 3:
            raise RunLogError(f"Field 'review_rounds' must be an integer between 0 and 3 or null, got {rounds!r}")
        if rev_res in ("approved", "changes_requested") and rounds < 1:
            raise RunLogError(
                f"Field 'review_rounds' must be between 1 and 3 when review_result is '{rev_res}', got {rounds!r}"
            )

    # 10. reviewer_model: non-empty string or None
    rev_model = record["reviewer_model"]
    if rev_model is not None:
        if not isinstance(rev_model, str) or not rev_model.strip():
            raise RunLogError(f"Field 'reviewer_model' must be a non-empty string or null, got {rev_model!r}")


def record_run(
    *,
    issue: Any,
    result: str,
    builder: str,
    auditor: str,
    pr: Optional[Any] = None,
    kickoff_at: Optional[str] = None,
    pr_opened_at: Optional[str] = None,
    first_review_at: Optional[str] = None,
    merged_at: Optional[str] = None,
    human_intervened: Any = False,
    pr_score: Optional[float] = None,
    review_result: Optional[str] = None,
    review_rounds: Optional[int] = None,
    reviewer_model: Optional[str] = None,
    runs_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Atomically appends a validated run log record to .factory/runs/runs.jsonl."""
    runs_path = runs_dir or resolve_runs_dir()
    runs_file = runs_path / "runs.jsonl"

    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "issue": issue,
        "pr": pr,
        "kickoff_at": kickoff_at or now_iso,
        "pr_opened_at": pr_opened_at,
        "first_review_at": first_review_at,
        "merged_at": merged_at,
        "human_intervened": human_intervened,
        "result": result,
        "builder": builder,
        "auditor": auditor,
        "pr_score": pr_score,
        "review_result": review_result,
        "review_rounds": review_rounds,
        "reviewer_model": reviewer_model,
    }

    validate_run_record(record)

    with runs_lock(runs_path):
        line = json.dumps(record, separators=(",", ":")) + "\n"
        with open(runs_file, "a", encoding="utf-8") as rf:
            rf.write(line)
            rf.flush()
            os.fsync(rf.fileno())

    return record


def read_runs(runs_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Reads all run records from .factory/runs/runs.jsonl."""
    runs_path = runs_dir or resolve_runs_dir()
    runs_file = runs_path / "runs.jsonl"
    if not runs_file.exists():
        return []

    with runs_lock(runs_path):
        with open(runs_file, "r", encoding="utf-8") as rf:
            records = [json.loads(line) for line in rf if line.strip()]

    return records
