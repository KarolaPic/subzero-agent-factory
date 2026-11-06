import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_run import evaluate_merged_pr, record_run_outcome
from scripts.run_log import read_runs, validate_run_record


class TestEvaluateRun(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_eval_run_")
        self.repo_root = Path(self.test_dir)
        self.mem_dir = self.repo_root / ".factory" / "memory"
        self.mem_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir = self.repo_root / ".factory" / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

        # Create dummy work-item
        items_dir = self.repo_root / ".factory" / "work-items"
        items_dir.mkdir(parents=True, exist_ok=True)
        work_item = {
            "id": "gh-99",
            "issueNumber": 40,
            "source": "https://github.com/cesarchavezcal/subzero-agent-factory/issues/40",
            "label": "agent",
            "stage": "complete",
            "status": "complete",
            "builder": "poteto-mode",
            "playbook": "autopilot-full",
            "primarySkill": "implement-ticket",
            "planPath": "plans/gh-99.md",
            "ticketIds": [],
            "verifySkill": "verify-app",
            "evidenceDir": "artifacts/gh-99",
            "pendingQuestions": [],
            "blockers": ["Clarified requirements with human"],
            "decisions": [],
            "retryCount": 1,
            "waitingOn": "none",
            "prScore": 9.4,
            "builderModel": "gemini-3.8-flash-high",
            "auditorModel": "grok-4.7",
        }
        with open(items_dir / "gh-99.json", "w", encoding="utf-8") as f:
            json.dump(work_item, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_evaluate_merged_pr_records_lesson_and_run_log(self):
        res = evaluate_merged_pr(
            pr_number=99,
            pr_url="https://github.com/cesarchavezcal/subzero-agent-factory/pull/99",
            mem_dir=self.mem_dir,
            runs_dir=self.runs_dir,
            repo_root=self.repo_root,
        )
        self.assertEqual(res["prNumber"], 99)
        self.assertEqual(res["lessonsRecorded"], 1)
        self.assertEqual(res["lessons"][0]["workItemId"], "gh-99")

        # Verify runLog returned in response
        self.assertIn("runLog", res)
        run_log = res["runLog"]
        self.assertEqual(run_log["issue"], 40)
        self.assertEqual(run_log["pr"], 99)
        self.assertEqual(run_log["result"], "merged")
        self.assertEqual(run_log["builder"], "gemini-3.8-flash-high")
        self.assertEqual(run_log["auditor"], "grok-4.7")
        self.assertEqual(run_log["pr_score"], 9.4)
        self.assertEqual(run_log["human_intervened"], {"occurred": True, "count": 1})

        # Verify run record in runs.jsonl file
        runs = read_runs(self.runs_dir)
        self.assertEqual(len(runs), 1)
        validate_run_record(runs[0])

    def test_record_run_outcome_blocked_and_failed(self):
        # 1. Blocked run
        rec_blocked = record_run_outcome(
            issue=101,
            result="blocked",
            builder="gemini-3.8-flash-high",
            auditor="grok-4.7",
            runs_dir=self.runs_dir,
            repo_root=self.repo_root,
        )
        self.assertEqual(rec_blocked["result"], "blocked")
        self.assertIsNone(rec_blocked["merged_at"])

        # 2. Failed run
        rec_failed = record_run_outcome(
            issue=102,
            result="failed",
            builder="gemini-3.8-flash-high",
            auditor="grok-4.7",
            runs_dir=self.runs_dir,
            repo_root=self.repo_root,
        )
        self.assertEqual(rec_failed["result"], "failed")

        runs = read_runs(self.runs_dir)
        self.assertEqual(len(runs), 2)
        for r in runs:
            validate_run_record(r)


if __name__ == "__main__":
    unittest.main()
