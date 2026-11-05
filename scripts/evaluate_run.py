#!/usr/bin/env python3
"""Post-merge evaluation runner for Grok Bot Agent Factory.

Inspects merged pull requests, extracts diff and work-item evidence,
records lessons into the Memory Store, writes run logs to .factory/runs/runs.jsonl,
and checks for threshold readiness.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.evaluator import evaluate_work_item
from scripts.memory_store import get_ready_patterns, resolve_memory_dir
from scripts.run_log import read_runs, record_run, resolve_runs_dir


def load_models_config(root: Optional[Path] = None) -> Dict[str, str]:
    """Loads configured models from models.yml if present."""
    base = root or Path.cwd()
    models_file = base / "models.yml"
    if models_file.exists():
        try:
            import yaml
            with open(models_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {
        "builder": "gemini-3.8-flash-high",
        "auditor": "grok-4.7",
        "planner": "gemini-3.8-flash-high",
        "epic_planner": "gemini-3.8-flash-high",
        "subagents": "gemini-3.8-flash-high",
    }


def record_run_outcome(
    *,
    issue: Any,
    result: str,
    pr: Optional[Any] = None,
    work_item: Optional[Dict[str, Any]] = None,
    builder: Optional[str] = None,
    auditor: Optional[str] = None,
    pr_score: Optional[float] = None,
    runs_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Records an agent run outcome (merged, blocked, or failed) to .factory/runs/runs.jsonl."""
    root = repo_root or Path.cwd()
    models = load_models_config(root)
    wi = work_item or {}

    builder_model = builder or wi.get("builderModel") or models.get("builder", "gemini-3.8-flash-high")
    auditor_model = auditor or wi.get("auditorModel") or models.get("auditor", "grok-4.7")

    now_iso = datetime.now(timezone.utc).isoformat()
    kickoff = wi.get("startedAt") or wi.get("createdAt") or now_iso
    pr_opened = wi.get("prOpenedAt") or None
    first_review = wi.get("firstReviewAt") or None
    merged = now_iso if result == "merged" else wi.get("mergedAt") or None

    blockers = wi.get("blockers", [])
    interventions = wi.get("humanInterventions", [])
    hi_count = len(blockers) + len(interventions)
    hi_occurred = hi_count > 0 or bool(wi.get("humanIntervened", False))

    target_runs_dir = runs_dir or resolve_runs_dir(root)

    return record_run(
        issue=issue,
        pr=pr,
        kickoff_at=kickoff,
        pr_opened_at=pr_opened,
        first_review_at=first_review,
        merged_at=merged,
        human_intervened={"occurred": hi_occurred, "count": hi_count},
        result=result,
        builder=builder_model,
        auditor=auditor_model,
        pr_score=pr_score if pr_score is not None else wi.get("prScore"),
        runs_dir=target_runs_dir,
    )


def evaluate_merged_pr(
    *,
    pr_number: int,
    pr_url: Optional[str] = None,
    mem_dir: Optional[Path] = None,
    runs_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Evaluates a merged PR against factory rubrics, updates memory store, and records run log."""
    root = repo_root or Path.cwd()
    memory_path = mem_dir or resolve_memory_dir(root)
    runs_path = runs_dir or resolve_runs_dir(root)

    # 1. Obtain merge diff if git is available
    diff_text = ""
    try:
        diff_text = subprocess.check_output(
            ["git", "diff", "HEAD~1", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

    # 2. Locate associated work-item JSON if present
    work_item_id = f"gh-{pr_number}"
    work_item_file = root / ".factory" / "work-items" / f"{work_item_id}.json"
    if work_item_file.exists():
        with open(work_item_file, "r", encoding="utf-8") as f:
            work_item = json.load(f)
    else:
        work_item = {
            "id": work_item_id,
            "prUrl": pr_url,
            "primarySkill": "implement-ticket",
            "retryCount": 0,
            "blockers": [],
        }

    # 3. Read audit log if present
    audit_file = root / "artifacts" / work_item_id / "audit.log"
    audit_log = None
    if audit_file.exists():
        with open(audit_file, "r", encoding="utf-8") as af:
            audit_log = af.read()

    # 4. Evaluate memory lessons
    lessons = evaluate_work_item(
        work_item,
        audit_log=audit_log,
        diff_text=diff_text,
        mem_dir=memory_path,
    )

    ready_patterns = get_ready_patterns(memory_path)

    # 5. Record run outcome to .factory/runs/runs.jsonl
    issue_id = work_item.get("issueNumber") or work_item.get("issue") or pr_number
    run_log_entry = record_run_outcome(
        issue=issue_id,
        result="merged",
        pr=pr_number,
        work_item=work_item,
        runs_dir=runs_path,
        repo_root=root,
    )

    return {
        "prNumber": pr_number,
        "lessonsRecorded": len(lessons),
        "lessons": [l["lesson"] for l in lessons],
        "readyPatterns": ready_patterns,
        "runLog": run_log_entry,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate merged PR, update factory memory, and record run log.")
    parser.add_argument("--pr-number", type=int, required=True, help="Merged PR number")
    parser.add_argument("--pr-url", type=str, default=None, help="PR HTML URL")
    args = parser.parse_args()

    result = evaluate_merged_pr(pr_number=args.pr_number, pr_url=args.pr_url)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
