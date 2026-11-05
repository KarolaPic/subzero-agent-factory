import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.review_pr import (
    MaxRoundsExceededError,
    ModelConfigurationError,
    ReviewerError,
    TaskCardValidationError,
    evaluate_review,
    load_yaml_file,
    parse_diff_files,
    parse_task_card,
    resolve_and_validate_models,
    submit_formal_review,
)


class TestReviewPrSkill(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.skill_path = self.repo_root / ".agents" / "skills" / "review-pr" / "SKILL.md"

    def test_skill_file_exists(self):
        self.assertTrue(self.skill_path.is_file(), f"Missing skill file: {self.skill_path}")

    def test_frontmatter_metadata(self):
        content = self.skill_path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        self.assertIsNotNone(match, "Frontmatter missing or invalid")
        frontmatter = match.group(1)
        self.assertIn("name: review-pr", frontmatter)
        self.assertIn("description:", frontmatter)

    def test_auditor_model_and_invariants(self):
        content = self.skill_path.read_text(encoding="utf-8")
        self.assertIn("models.yml", content)
        self.assertIn("auditor", content)
        self.assertIn("builder", content)
        self.assertIn("auditor != builder", content)
        # Check forbidden models invariant
        self.assertRegex(content, r"(?i)zero (claude|gpt|argon)")
        # Check no fallback
        self.assertRegex(content, r"(?i)no fallback")

    def test_task_card_and_diff_reading(self):
        content = self.skill_path.read_text(encoding="utf-8")
        self.assertIn("Goal", content)
        self.assertIn("Done when", content)
        self.assertIn("Don't touch", content)
        self.assertIn("diff", content.lower())
        self.assertIn("test", content.lower())

    def test_formal_review_submission_and_bot_identity(self):
        content = self.skill_path.read_text(encoding="utf-8")
        self.assertIn("APPROVE", content)
        self.assertIn("REQUEST_CHANGES", content)
        self.assertIn("gh pr review", content)
        self.assertRegex(content, r"(?i)github app|reviewer token")

    def test_max_rounds_loop_guard(self):
        content = self.skill_path.read_text(encoding="utf-8")
        self.assertIn("3 rounds", content)
        self.assertIn("César", content)

    def test_communication_and_branch_invariants(self):
        content = self.skill_path.read_text(encoding="utf-8")
        self.assertRegex(content, r"(?i)no bot comments")
        self.assertRegex(content, r"(?i)never delete branch")


class TestReviewPrEngine(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent

    def test_resolve_and_validate_models_success(self):
        models = resolve_and_validate_models(self.repo_root)
        self.assertIn("builder", models)
        self.assertIn("auditor", models)
        self.assertNotEqual(models["builder"], models["auditor"])
        for forbidden in ["argon", "claude", "gpt"]:
            self.assertNotIn(forbidden, models["builder"].lower())
            self.assertNotIn(forbidden, models["auditor"].lower())

    def test_resolve_models_fails_if_auditor_equals_builder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            (tmp_root / "models.yml").write_text(
                "builder: gemini-3.8-flash-high\nauditor: gemini-3.8-flash-high\n",
                encoding="utf-8",
            )
            with self.assertRaises(ModelConfigurationError) as ctx:
                resolve_and_validate_models(tmp_root)
            self.assertIn("cannot be the same", str(ctx.exception))

    def test_resolve_models_rejects_forbidden_models(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            (tmp_root / "models.yml").write_text(
                "builder: claude-3-opus\nauditor: grok-4.7\n",
                encoding="utf-8",
            )
            with self.assertRaises(ModelConfigurationError) as ctx:
                resolve_and_validate_models(tmp_root)
            self.assertIn("Forbidden model", str(ctx.exception))

    def test_parse_task_card_valid(self):
        card = (
            "## Goal\nImplement review skill.\n\n"
            "## Done when\n- [ ] Skill exists\n- [x] Engine passes tests\n\n"
            "## Don't touch\n- models.yml defaults\n- Never delete branches\n"
        )
        parsed = parse_task_card(card)
        self.assertEqual(parsed["goal"], "Implement review skill.")
        self.assertEqual(len(parsed["done_when"]), 2)
        self.assertEqual(parsed["done_when"][0], "Skill exists")
        self.assertEqual(parsed["done_when"][1], "Engine passes tests")
        self.assertEqual(len(parsed["dont_touch"]), 2)
        self.assertEqual(parsed["dont_touch"][0], "models.yml defaults")
        self.assertEqual(parsed["dont_touch"][1], "Never delete branches")

    def test_parse_task_card_missing_sections(self):
        with self.assertRaises(TaskCardValidationError):
            parse_task_card("## Goal\nSome goal without Done when or Don't touch")

        with self.assertRaises(TaskCardValidationError):
            parse_task_card("## Done when\n- [ ] item\n## Don't touch\n- item")

        with self.assertRaises(TaskCardValidationError):
            parse_task_card("")

    def test_parse_diff_files(self):
        diff = (
            "diff --git a/scripts/review_pr.py b/scripts/review_pr.py\n"
            "new file mode 100755\n"
            "--- /dev/null\n"
            "+++ b/scripts/review_pr.py\n"
            "@@ -0,0 +1,50 @@\n"
            "+# reviewer code\n"
            "diff --git a/tests/test_review_pr.py b/tests/test_review_pr.py\n"
            "--- a/tests/test_review_pr.py\n"
            "+++ b/tests/test_review_pr.py\n"
        )
        files = parse_diff_files(diff)
        self.assertEqual(files, ["scripts/review_pr.py", "tests/test_review_pr.py"])

    def test_evaluate_review_approval(self):
        task_card = {
            "goal": "Add reviewer agent skill and engine",
            "done_when": ["Skill exists", "Tests pass"],
            "dont_touch": ["models.yml defaults", "Never delete branches"],
        }
        diff = "diff --git a/scripts/review_pr.py b/scripts/review_pr.py\n+print('hello')"
        test_evidence = "Ran 90 tests in 5s\nOK\nexitCode === 0"

        eval_res = evaluate_review(diff, task_card, test_evidence, round_num=1, max_rounds=3)
        self.assertEqual(eval_res["verdict"], "APPROVE")
        self.assertEqual(len(eval_res["findings"]), 0)
        self.assertFalse(eval_res["halted"])
        self.assertIn("Approved", eval_res["summary"])

    def test_evaluate_review_test_failure(self):
        task_card = {
            "goal": "Add reviewer agent skill and engine",
            "done_when": ["Skill exists", "Tests pass"],
            "dont_touch": ["models.yml defaults"],
        }
        diff = "diff --git a/scripts/review_pr.py b/scripts/review_pr.py\n+print('hello')"
        test_evidence = "FAILED (failures=2, errors=0)"

        eval_res = evaluate_review(diff, task_card, test_evidence, round_num=1, max_rounds=3)
        self.assertEqual(eval_res["verdict"], "REQUEST_CHANGES")
        self.assertIn("Test verification evidence indicates test failures", eval_res["findings"][0])
        self.assertFalse(eval_res["halted"])

    def test_evaluate_review_missing_test_evidence(self):
        task_card = {
            "goal": "Add reviewer agent skill and engine",
            "done_when": ["Skill exists"],
            "dont_touch": ["models.yml"],
        }
        diff = "diff --git a/scripts/review_pr.py b/scripts/review_pr.py\n+print('hello')"

        eval_res = evaluate_review(diff, task_card, test_evidence=None, round_num=1, max_rounds=3)
        self.assertEqual(eval_res["verdict"], "REQUEST_CHANGES")
        self.assertTrue(any("Missing test verification evidence" in f for f in eval_res["findings"]))

    def test_evaluate_review_violates_dont_touch(self):
        task_card = {
            "goal": "Feature",
            "done_when": ["Done"],
            "dont_touch": ["models.yml defaults"],
        }
        diff = "diff --git a/models.yml b/models.yml\n+tampered"
        test_evidence = "OK\nexitCode === 0"

        eval_res = evaluate_review(diff, task_card, test_evidence, round_num=1, max_rounds=3)
        self.assertEqual(eval_res["verdict"], "REQUEST_CHANGES")
        self.assertTrue(any("models.yml was modified" in f for f in eval_res["findings"]))

    def test_evaluate_review_max_rounds_escalation(self):
        task_card = {
            "goal": "Feature",
            "done_when": ["Done"],
            "dont_touch": ["models.yml"],
        }
        diff = "diff --git a/test.py b/test.py\n+print('test')"
        test_evidence = "OK\nexitCode === 0"

        # Round 4 of 3 -> Halts!
        eval_res = evaluate_review(diff, task_card, test_evidence, round_num=4, max_rounds=3)
        self.assertEqual(eval_res["verdict"], "REQUEST_CHANGES")
        self.assertTrue(eval_res["halted"])
        self.assertTrue(any("exceeded maximum permitted rounds" in f for f in eval_res["findings"]))
        self.assertIn("César", eval_res["summary"])

    @patch("subprocess.run")
    def test_submit_formal_review_approve(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        res = submit_formal_review(
            pr_number=69,
            verdict="APPROVE",
            body="Looks good",
            token="ghp_mocktoken123",
            dry_run=False,
        )
        self.assertTrue(res["submitted"])
        self.assertEqual(res["verdict"], "APPROVE")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertIn("gh", cmd)
        self.assertIn("pr", cmd)
        self.assertIn("review", cmd)
        self.assertIn("69", cmd)
        self.assertIn("--approve", cmd)
        self.assertIn("--body", cmd)

    @patch("subprocess.run")
    def test_submit_formal_review_request_changes(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        res = submit_formal_review(
            pr_number=69,
            verdict="REQUEST_CHANGES",
            body="Needs fixes",
            token="ghp_mocktoken123",
            dry_run=False,
        )
        self.assertTrue(res["submitted"])
        self.assertEqual(res["verdict"], "REQUEST_CHANGES")
        cmd = mock_run.call_args[0][0]
        self.assertIn("--request-changes", cmd)

    def test_submit_formal_review_dry_run(self):
        res = submit_formal_review(
            pr_number=69,
            verdict="APPROVE",
            body="Dry run body",
            dry_run=True,
        )
        self.assertFalse(res["submitted"])
        self.assertTrue(res["dry_run"])
        self.assertEqual(res["verdict"], "APPROVE")

    def test_cli_execution_dry_run_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            diff_file = Path(tmpdir) / "test.diff"
            diff_file.write_text("diff --git a/foo.py b/foo.py\n+print(1)\n", encoding="utf-8")

            tc_file = Path(tmpdir) / "task_card.md"
            tc_file.write_text(
                "## Goal\nTest CLI\n\n## Done when\n- [ ] Step 1\n\n## Don't touch\n- None\n",
                encoding="utf-8",
            )

            te_file = Path(tmpdir) / "test_evidence.txt"
            te_file.write_text("OK\nexitCode === 0\n", encoding="utf-8")

            cmd = [
                "python3",
                str(self.repo_root / "scripts" / "review_pr.py"),
                "--diff",
                str(diff_file),
                "--task-card",
                str(tc_file),
                "--test-evidence",
                str(te_file),
                "--round",
                "1",
                "--max-rounds",
                "3",
                "--dry-run",
                "--json",
            ]

            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, f"CLI error: {proc.stderr}")
            data = json.loads(proc.stdout)
            self.assertEqual(data["verdict"], "APPROVE")
            self.assertEqual(data["round"], 1)
            self.assertEqual(data["max_rounds"], 3)
            self.assertFalse(data["halted"])
            self.assertTrue(data["dry_run"])

    def test_cli_execution_halted_exit_code_2(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            diff_file = Path(tmpdir) / "test.diff"
            diff_file.write_text("diff --git a/foo.py b/foo.py\n+print(1)\n", encoding="utf-8")

            tc_file = Path(tmpdir) / "task_card.md"
            tc_file.write_text(
                "## Goal\nTest CLI\n\n## Done when\n- [ ] Step 1\n\n## Don't touch\n- None\n",
                encoding="utf-8",
            )

            te_file = Path(tmpdir) / "test_evidence.txt"
            te_file.write_text("OK\nexitCode === 0\n", encoding="utf-8")

            cmd = [
                "python3",
                str(self.repo_root / "scripts" / "review_pr.py"),
                "--diff",
                str(diff_file),
                "--task-card",
                str(tc_file),
                "--test-evidence",
                str(te_file),
                "--round",
                "4",
                "--max-rounds",
                "3",
                "--dry-run",
                "--json",
            ]

            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2, f"Expected returncode 2, got: {proc.returncode}")
            data = json.loads(proc.stdout)
            self.assertEqual(data["verdict"], "REQUEST_CHANGES")
            self.assertTrue(data["halted"])


if __name__ == "__main__":
    unittest.main()
