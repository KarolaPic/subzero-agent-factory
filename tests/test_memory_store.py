import json
import multiprocessing
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.memory_store import record_lesson, get_ready_patterns, resolve_memory_dir


def _worker_append(args):
    mem_dir, worker_id, iterations = args
    for i in range(iterations):
        record_lesson(
            work_item_id=f"gh-w{worker_id}-{i}",
            target_skill="poteto-mode",
            failure_class="audit_interrogation_failure",
            rubric_violated="principle-fix-root-causes",
            evidence_summary=f"Worker {worker_id} iteration {i}",
            mem_dir=Path(mem_dir),
            threshold=5,
        )


class TestMemoryStore(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_mem_store_")
        self.mem_dir = Path(self.test_dir) / ".factory" / "memory"
        self.mem_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_record_lesson_basic_and_threshold(self):
        # 1. First record
        res1 = record_lesson(
            work_item_id="gh-1",
            target_skill="poteto-mode",
            failure_class="audit_interrogation_failure",
            rubric_violated="principle-fix-root-causes",
            evidence_summary="Null guard added in index.ts without root-cause fix",
            pr_url="https://github.com/cesarchavezcal/subzero-agent-factory/pull/1",
            threshold=3,
            mem_dir=self.mem_dir,
        )
        self.assertEqual(res1["pattern"]["count"], 1)
        self.assertFalse(res1["pattern"]["readyForRoutineMaker"])
        self.assertEqual(res1["pattern"]["status"], "observing")

        # 2. Second record
        res2 = record_lesson(
            work_item_id="gh-2",
            target_skill="poteto-mode",
            failure_class="audit_interrogation_failure",
            rubric_violated="principle-fix-root-causes",
            evidence_summary="Band-aid fix repeated in utils.ts",
            threshold=3,
            mem_dir=self.mem_dir,
        )
        self.assertEqual(res2["pattern"]["count"], 2)
        self.assertFalse(res2["pattern"]["readyForRoutineMaker"])

        # 3. Third record triggers threshold
        res3 = record_lesson(
            work_item_id="gh-3",
            target_skill="poteto-mode",
            failure_class="audit_interrogation_failure",
            rubric_violated="principle-fix-root-causes",
            evidence_summary="Third band-aid fix",
            threshold=3,
            mem_dir=self.mem_dir,
        )
        self.assertEqual(res3["pattern"]["count"], 3)
        self.assertTrue(res3["pattern"]["readyForRoutineMaker"])
        self.assertEqual(res3["pattern"]["status"], "threshold_reached")

        # Verify lessons.jsonl content
        lessons_file = self.mem_dir / "lessons.jsonl"
        self.assertTrue(lessons_file.exists())
        with open(lessons_file, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0]["workItemId"], "gh-1")
        self.assertEqual(lines[2]["workItemId"], "gh-3")

        # Verify get_ready_patterns
        ready = get_ready_patterns(self.mem_dir)
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0]["patternId"], "audit_interrogation_failure::poteto-mode")

    def test_multiprocess_concurrency(self):
        num_workers = 3
        iterations = 5
        total_records = num_workers * iterations

        args_list = [(str(self.mem_dir), w, iterations) for w in range(num_workers)]
        with multiprocessing.Pool(processes=num_workers) as pool:
            pool.map(_worker_append, args_list)

        lessons_file = self.mem_dir / "lessons.jsonl"
        with open(lessons_file, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(lines), total_records)

        patterns_file = self.mem_dir / "patterns.json"
        with open(patterns_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        pattern = data["patterns"]["audit_interrogation_failure::poteto-mode"]
        self.assertEqual(pattern["count"], total_records)
        self.assertEqual(len(pattern["lessonIds"]), total_records)
        self.assertTrue(pattern["readyForRoutineMaker"])


if __name__ == "__main__":
    unittest.main()
