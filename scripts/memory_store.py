#!/usr/bin/env python3
"""Thread- and process-safe Memory Store client for Grok Bot Agent Factory.

Provides atomic appends to lessons.jsonl and atomic index updates to patterns.json
across concurrent Git worktrees on macOS and Linux using fcntl.flock and a dedicated lockfile.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional


DEFAULT_GLOBAL_MEMORY_DIR = Path(
    os.environ.get("FACTORY_GLOBAL_MEMORY_DIR", str(Path.home() / ".factory" / "memory"))
).resolve()


class MemoryStoreError(Exception):
    """Base exception for MemoryStore failures."""


def resolve_memory_dir(
    cwd: Optional[Path] = None,
    tier: str = "global",
) -> Path:
    """Resolves the canonical memory directory (global ~/.factory/memory or project-local .factory/memory)."""
    if tier == "local":
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
            repo_root = Path(cwd or Path.cwd()).resolve()

        mem_dir = repo_root / ".factory" / "memory"
    else:
        # Global memory tier: ~/.factory/memory or FACTORY_GLOBAL_MEMORY_DIR
        mem_dir = Path(
            os.environ.get("FACTORY_GLOBAL_MEMORY_DIR", str(Path.home() / ".factory" / "memory"))
        ).resolve()

    mem_dir.mkdir(parents=True, exist_ok=True)
    return mem_dir


@contextlib.contextmanager
def memory_lock(mem_dir: Path, timeout_seconds: float = 15.0) -> Generator[None, None, None]:
    """Acquires an exclusive advisory lock on the dedicated .memory.lock file."""
    lock_file = mem_dir / ".memory.lock"
    fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o644)
    start_time = time.monotonic()

    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except (BlockingIOError, OSError):
            if time.monotonic() - start_time >= timeout_seconds:
                os.close(fd)
                raise TimeoutError(f"Timed out after {timeout_seconds}s waiting for memory store lock at {lock_file}")
            time.sleep(0.05)

    try:
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def record_lesson(
    *,
    work_item_id: str,
    target_skill: str,
    failure_class: str,
    rubric_violated: str,
    evidence_summary: str,
    pr_url: Optional[str] = None,
    status: str = "active",
    threshold: int = 3,
    mem_dir: Optional[Path] = None,
    tier: str = "global",
) -> Dict[str, Any]:
    """Atomically appends a lesson record and updates the aggregated pattern index."""
    memory_path = mem_dir or resolve_memory_dir(tier=tier)
    now_iso = datetime.now(timezone.utc).isoformat()
    lesson_id = f"les-{uuid.uuid4().hex[:12]}"

    lesson_record = {
        "id": lesson_id,
        "timestamp": now_iso,
        "workItemId": work_item_id,
        "prUrl": pr_url,
        "targetSkill": target_skill,
        "failureClass": failure_class,
        "rubricViolated": rubric_violated,
        "evidenceSummary": evidence_summary[:8192],
        "status": status,
    }

    lessons_file = memory_path / "lessons.jsonl"
    patterns_file = memory_path / "patterns.json"

    with memory_lock(memory_path):
        # 1. Atomic Append to lessons.jsonl
        line = json.dumps(lesson_record, separators=(",", ":")) + "\n"
        with open(lessons_file, "a", encoding="utf-8") as lf:
            lf.write(line)
            lf.flush()
            os.fsync(lf.fileno())

        # 2. Read patterns.json
        if patterns_file.exists():
            with open(patterns_file, "r", encoding="utf-8") as pf:
                pat_data = json.load(pf)
        else:
            pat_data = {
                "version": "1.0.0",
                "updatedAt": now_iso,
                "threshold": threshold,
                "patterns": {},
            }

        # 3. Update Aggregate Index
        pattern_key = f"{failure_class}::{target_skill}"
        if pattern_key not in pat_data["patterns"]:
            pat_data["patterns"][pattern_key] = {
                "patternId": pattern_key,
                "failureClass": failure_class,
                "targetSkill": target_skill,
                "count": 0,
                "lessonIds": [],
                "readyForRoutineMaker": False,
                "firstSeen": now_iso,
                "lastSeen": now_iso,
                "rubricsViolated": [],
                "routineId": None,
                "status": "observing",
            }

        entry = pat_data["patterns"][pattern_key]
        entry["count"] += 1
        if lesson_id not in entry["lessonIds"]:
            entry["lessonIds"].append(lesson_id)
        entry["lastSeen"] = now_iso

        if rubric_violated not in entry.get("rubricsViolated", []):
            entry.setdefault("rubricsViolated", []).append(rubric_violated)

        if entry["count"] >= pat_data.get("threshold", threshold):
            entry["readyForRoutineMaker"] = True
            if entry["status"] == "observing":
                entry["status"] = "threshold_reached"

        pat_data["updatedAt"] = now_iso

        # 4. Atomic Replace patterns.json via temp file on same filesystem
        temp_file = memory_path / f"patterns.json.tmp.{os.getpid()}.{uuid.uuid4().hex}"
        try:
            with open(temp_file, "w", encoding="utf-8") as tf:
                json.dump(pat_data, tf, indent=2)
                tf.flush()
                os.fsync(tf.fileno())
            os.replace(temp_file, patterns_file)
        finally:
            if temp_file.exists():
                with contextlib.suppress(OSError):
                    temp_file.unlink()

    return {"lesson": lesson_record, "pattern": entry}


def get_ready_patterns(
    mem_dir: Optional[Path] = None,
    tier: str = "global",
) -> List[Dict[str, Any]]:
    """Returns all patterns where readyForRoutineMaker is true and not yet routine_synthesized."""
    memory_path = mem_dir or resolve_memory_dir(tier=tier)
    patterns_file = memory_path / "patterns.json"
    if not patterns_file.exists():
        return []

    with memory_lock(memory_path):
        with open(patterns_file, "r", encoding="utf-8") as pf:
            pat_data = json.load(pf)

    ready = []
    for entry in pat_data.get("patterns", {}).values():
        if entry.get("readyForRoutineMaker") and entry.get("status") != "routine_synthesized":
            ready.append(entry)
    return ready
