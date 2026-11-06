import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.evaluator import evaluate_work_item, evaluate_work_item_file


class TestEvaluator(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_evaluator_")
        self.mem_dir = Path(self.test_dir) / ".factory" / "memory"
        self.mem_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_evaluate_clean_run(self):
        clean_work_item = {
            "id": "gh-10",
            "source": "https://github.com/cesarchavezcal/subzero-agent-factory/issues/10",
            "label": "agent",
            "stage": "complete",
            "status": "complete",
            "builder": "poteto-mode",
            "playbook": "autopilot-full",
            "primarySkill": "implement-ticket",
            "planPath": "plans/gh-10.md",
            "ticketIds": [],
            "verifySkill": "verify-app",
            "evidenceDir": "artifacts/gh-10",
            "pendingQuestions": [],
            "blockers": [],
            "decisions": [],
            "retryCount": 0,
            "waitingOn": "none",
        }
        res = evaluate_work_item(clean_work_item, mem_dir=self.mem_dir)
        self.assertEqual(len(res), 0)

    def test_evaluate_rework_failure(self):
        rework_item = {
            "id": "gh-11",
            "source": "https://github.com/cesarchavezcal/subzero-agent-factory/issues/11",
            "label": "agent",
            "stage": "complete",
            "status": "complete",
            "builder": "poteto-mode",
            "playbook": "autopilot-full",
            "primarySkill": "fix-bug",
            "planPath": "plans/gh-11.md",
            "ticketIds": [],
            "verifySkill": "verify-app",
            "evidenceDir": "artifacts/gh-11",
            "pendingQuestions": [],
            "blockers": [],
            "decisions": [],
            "retryCount": 2,
            "waitingOn": "none",
        }
        res = evaluate_work_item(
            rework_item,
            audit_log="Audit failed on unit test mocking.",
            mem_dir=self.mem_dir,
        )
        self.assertEqual(len(res), 1)
        lesson = res[0]["lesson"]
        self.assertEqual(lesson["failureClass"], "audit_interrogation_failure")
        self.assertEqual(lesson["rubricViolated"], "rework_frequency")
        self.assertIn("required 2 rework retry attempts", lesson["evidenceSummary"])

    def test_evaluate_reproduction_blocker(self):
        blocked_item = {
            "id": "gh-12",
            "source": "https://github.com/cesarchavezcal/subzero-agent-factory/issues/12",
            "label": "agent",
            "stage": "scouting",
            "status": "blocked",
            "builder": "poteto-mode",
            "playbook": "autopilot-full",
            "primarySkill": "fix-bug",
            "planPath": "plans/gh-12.md",
            "ticketIds": [],
            "verifySkill": "verify-app",
            "evidenceDir": "artifacts/gh-12",
            "pendingQuestions": [],
            "blockers": ["Cannot reproduce defect on clean checkout."],
            "decisions": [],
            "retryCount": 0,
            "waitingOn": "blocked",
        }
        res = evaluate_work_item(blocked_item, mem_dir=self.mem_dir)
        self.assertEqual(len(res), 1)
        lesson = res[0]["lesson"]
        self.assertEqual(lesson["failureClass"], "reproduction_failure")
        self.assertEqual(lesson["rubricViolated"], "plan_then_build")


if __name__ == "__main__":
    unittest.main()
