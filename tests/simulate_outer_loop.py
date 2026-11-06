#!/usr/bin/env python3
"""End-to-end integration simulation script for Grok Bot Agent Factory Outer Loop."""

import json
import multiprocessing
import shutil
import tempfile
from pathlib import Path

from scripts.evaluator import evaluate_work_item
from scripts.memory_store import get_ready_patterns, record_lesson
from scripts.routine_maker import (
    generate_receipt_of_causality,
    load_lessons,
    mark_pattern_synthesized,
)


def _worker_stress(args):
    m_dir, wid = args
    for i in range(10):
        record_lesson(
            work_item_id=f"gh-stress-{wid}-{i}",
            target_skill="fix-bug",
            failure_class="concurrency_test",
            rubric_violated="test_seam_integrity",
            evidence_summary="stress test append",
            threshold=50,
            mem_dir=Path(m_dir),
        )


def run_simulation():
    test_root = tempfile.mkdtemp(prefix="sim_outer_loop_")
    try:
        mem_dir = Path(test_root) / ".factory" / "memory"
        mem_dir.mkdir(parents=True, exist_ok=True)
        print(f"[Step 1] Initialized isolated test store in {mem_dir}")

        key = "audit_interrogation_failure::poteto-mode"

        # Simulation Run 1
        item_1 = {
            "id": "gh-101",
            "primarySkill": "poteto-mode",
            "retryCount": 2,
            "prUrl": "https://github.com/cesarchavezcal/subzero-agent-factory/pull/101",
        }
        evaluate_work_item(
            item_1,
            audit_log="Audit rejected: band-aid fix added without root cause fix",
            mem_dir=mem_dir,
            threshold=3,
        )
        pats = json.load(open(mem_dir / "patterns.json"))["patterns"]
        print(f"[Step 2] Run 1 completed. Pattern count: {pats[key]['count']}, status: {pats[key]['status']}, ready: {pats[key]['readyForRoutineMaker']}")
        assert pats[key]["count"] == 1 and not pats[key]["readyForRoutineMaker"]

        # Simulation Run 2
        item_2 = {
            "id": "gh-102",
            "primarySkill": "poteto-mode",
            "retryCount": 1,
            "prUrl": "https://github.com/cesarchavezcal/subzero-agent-factory/pull/102",
        }
        evaluate_work_item(
            item_2,
            audit_log="Audit rejected: null guard added in index.ts instead of parser",
            mem_dir=mem_dir,
            threshold=3,
        )
        pats = json.load(open(mem_dir / "patterns.json"))["patterns"]
        print(f"[Step 3] Run 2 completed. Pattern count: {pats[key]['count']}, status: {pats[key]['status']}, ready: {pats[key]['readyForRoutineMaker']}")
        assert pats[key]["count"] == 2 and not pats[key]["readyForRoutineMaker"]

        # Simulation Run 3 (Threshold Breached)
        item_3 = {
            "id": "gh-103",
            "primarySkill": "poteto-mode",
            "retryCount": 1,
            "prUrl": "https://github.com/cesarchavezcal/subzero-agent-factory/pull/103",
        }
        evaluate_work_item(
            item_3,
            audit_log="Audit rejected: missing root-cause fix in state reducer",
            mem_dir=mem_dir,
            threshold=3,
        )
        pats = json.load(open(mem_dir / "patterns.json"))["patterns"]
        print(f"[Step 4] Run 3 completed. Pattern count: {pats[key]['count']}, status: {pats[key]['status']}, ready: {pats[key]['readyForRoutineMaker']}")
        assert pats[key]["count"] == 3 and pats[key]["readyForRoutineMaker"] and pats[key]["status"] == "threshold_reached"

        # Step 5: Routine Maker Receipt Synthesis
        ready = get_ready_patterns(mem_dir)
        assert len(ready) == 1
        lessons_map = load_lessons(mem_dir)
        receipt = generate_receipt_of_causality(ready[0], lessons_map)
        print("\n--- GENERATED RECEIPT OF CAUSALITY ---")
        print(receipt)
        print("--------------------------------------\n")

        # Step 6: Mark Pattern Synthesized
        mark_pattern_synthesized(mem_dir, key, routine_id="PR-26")
        pats_after = json.load(open(mem_dir / "patterns.json"))["patterns"]
        assert pats_after[key]["status"] == "routine_synthesized"
        assert pats_after[key]["routineId"] == "PR-26"
        print(f"[Step 7] Pattern marked synthesized: status={pats_after[key]['status']}, routineId={pats_after[key]['routineId']}")

        # Step 8: Multi-process concurrency torture test (5 workers x 10 records = 50 concurrent updates)
        worker_args = [(str(mem_dir), w) for w in range(5)]
        with multiprocessing.Pool(5) as p:
            p.map(_worker_stress, worker_args)

        stress_data = json.load(open(mem_dir / "patterns.json"))["patterns"]["concurrency_test::fix-bug"]
        print(f"[Step 8] Concurrency torture test: count={stress_data['count']}, total lessons={len(stress_data['lessonIds'])}")
        assert stress_data["count"] == 50
        assert len(stress_data["lessonIds"]) == 50

        print("\n[Step 9] Validating schemas against generated files...")
        # Verify JSONL lines can be read cleanly
        with open(mem_dir / "lessons.jsonl", "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        assert len(lines) == 53  # 3 from simulation + 50 from stress test
        print(f"Total verified lessons in ledger: {len(lines)}")

        print("\n✓ ALL SIMULATION STAGES COMPLETED AND VERIFIED CLEANLY.")
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


if __name__ == "__main__":
    run_simulation()
