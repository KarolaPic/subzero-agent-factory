"""Unit tests for scripts/classify_pr_risk.py.

Verifies diff risk classification rules:
- Docs-only PRs -> low-risk
- Tests-only PRs -> low-risk
- Small code fix (< 50 lines changed) with no protected paths -> low-risk
- Non-doc/test change >= 50 lines -> needs-approval
- Changes to protected paths (workflows, models, dependencies, factory config,
  skill evolution / AGENTS.md per ADR 0001) -> needs-approval
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

# Add repo root to import path so we can import classify_pr_risk directly
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import classify_pr_risk


class TestClassifyPRRisk(unittest.TestCase):
    def test_empty_diff_is_low_risk(self):
        res = classify_pr_risk.classify_file_stats([])
        self.assertEqual(res["classification"], "low-risk")
        self.assertTrue(res["is_low_risk"])
        self.assertEqual(res["total_changed_lines"], 0)

    def test_docs_only_is_low_risk_regardless_of_line_count(self):
        stats = [
            {"path": "README.md", "additions": 100, "deletions": 50},
            {"path": "docs/merge-policy.md", "additions": 200, "deletions": 10},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res["classification"], "low-risk")
        self.assertTrue(res["is_low_risk"])
        self.assertEqual(res["total_changed_lines"], 360)

    def test_tests_only_is_low_risk_regardless_of_line_count(self):
        stats = [
            {"path": "tests/test_models.py", "additions": 150, "deletions": 20},
            {"path": "tests/test_evaluator.py", "additions": 80, "deletions": 40},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res["classification"], "low-risk")
        self.assertTrue(res["is_low_risk"])
        self.assertEqual(res["total_changed_lines"], 290)

    def test_small_code_fix_under_50_lines_is_low_risk(self):
        stats = [
            {"path": "scripts/evaluator.py", "additions": 12, "deletions": 8},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res["classification"], "low-risk")
        self.assertTrue(res["is_low_risk"])
        self.assertEqual(res["total_changed_lines"], 20)

    def test_code_fix_at_50_lines_needs_approval(self):
        stats = [
            {"path": "scripts/evaluator.py", "additions": 30, "deletions": 20},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res["classification"], "needs-approval")
        self.assertFalse(res["is_low_risk"])
        self.assertEqual(res["total_changed_lines"], 50)
        self.assertTrue(any("50" in r for r in res["reasons"]))

    def test_code_fix_exceeding_50_lines_needs_approval(self):
        stats = [
            {"path": "scripts/evaluator.py", "additions": 45, "deletions": 15},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res["classification"], "needs-approval")
        self.assertFalse(res["is_low_risk"])
        self.assertEqual(res["total_changed_lines"], 60)

    def test_mixed_docs_and_code_under_50_lines_is_low_risk(self):
        stats = [
            {"path": "docs/setup.md", "additions": 5, "deletions": 2},
            {"path": "scripts/evaluator.py", "additions": 10, "deletions": 5},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res["classification"], "low-risk")
        self.assertTrue(res["is_low_risk"])
        self.assertEqual(res["total_changed_lines"], 22)

    def test_mixed_docs_and_code_over_50_lines_needs_approval(self):
        stats = [
            {"path": "docs/setup.md", "additions": 35, "deletions": 10},
            {"path": "scripts/evaluator.py", "additions": 10, "deletions": 10},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res["classification"], "needs-approval")
        self.assertFalse(res["is_low_risk"])
        self.assertEqual(res["total_changed_lines"], 65)

    def test_workflow_change_needs_approval_even_single_line(self):
        stats = [
            {"path": ".github/workflows/ci.yml", "additions": 1, "deletions": 1},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res["classification"], "needs-approval")
        self.assertFalse(res["is_low_risk"])
        self.assertTrue(any("workflow" in r.lower() for r in res["reasons"]))

    def test_model_configuration_change_needs_approval(self):
        stats = [
            {"path": "models.yml", "additions": 1, "deletions": 1},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res["classification"], "needs-approval")
        self.assertFalse(res["is_low_risk"])
        self.assertTrue(any("model" in r.lower() for r in res["reasons"]))

        stats_allowed = [
            {"path": "models.allowed.yml", "additions": 2, "deletions": 0},
        ]
        res_allowed = classify_pr_risk.classify_file_stats(stats_allowed)
        self.assertEqual(res_allowed["classification"], "needs-approval")

    def test_dependency_change_needs_approval(self):
        dep_files = [
            "package.json",
            "package-lock.json",
            "requirements.txt",
            "pyproject.toml",
            "go.mod",
            "Cargo.toml",
        ]
        for f in dep_files:
            with self.subTest(file=f):
                stats = [{"path": f, "additions": 1, "deletions": 0}]
                res = classify_pr_risk.classify_file_stats(stats)
                self.assertEqual(res["classification"], "needs-approval")
                self.assertFalse(res["is_low_risk"])

    def test_factory_core_config_needs_approval(self):
        stats = [
            {"path": ".factory/config.json", "additions": 1, "deletions": 1},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res["classification"], "needs-approval")
        self.assertFalse(res["is_low_risk"])

    def test_skill_evolution_and_agents_md_needs_approval_adr_0001(self):
        stats_skill = [
            {"path": ".agents/skills/implement-ticket/SKILL.md", "additions": 2, "deletions": 1},
        ]
        res_skill = classify_pr_risk.classify_file_stats(stats_skill)
        self.assertEqual(res_skill["classification"], "needs-approval")
        self.assertFalse(res_skill["is_low_risk"])

        stats_agents = [
            {"path": "AGENTS.md", "additions": 2, "deletions": 1},
        ]
        res_agents = classify_pr_risk.classify_file_stats(stats_agents)
        self.assertEqual(res_agents["classification"], "needs-approval")
        self.assertFalse(res_agents["is_low_risk"])

    def test_parse_numstat(self):
        numstat_text = (
            "10\t5\tscripts/evaluator.py\n"
            "20\t0\tREADME.md\n"
            "-\t-\tbinary_file.png\n"
        )
        parsed = classify_pr_risk.parse_numstat(numstat_text)
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0], {"path": "scripts/evaluator.py", "additions": 10, "deletions": 5})
        self.assertEqual(parsed[1], {"path": "README.md", "additions": 20, "deletions": 0})
        self.assertEqual(parsed[2], {"path": "binary_file.png", "additions": 0, "deletions": 0})

    def test_cli_execution_with_numstat_stdin(self):
        numstat_input = "2\t1\tREADME.md\n"
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "classify_pr_risk.py"), "--stdin"],
            input=numstat_input,
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["classification"], "low-risk")
        self.assertTrue(data["is_low_risk"])

    def test_cli_execution_label_only(self):
        numstat_input = "10\t5\t.github/workflows/ci.yml\n"
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "classify_pr_risk.py"), "--stdin", "--label"],
            input=numstat_input,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(proc.stdout.strip(), "needs-approval")

    def test_can_auto_merge_success_for_low_risk(self):
        stats = [{"path": "README.md", "additions": 10, "deletions": 2}]
        allowed, reason = classify_pr_risk.can_auto_merge(stats, ci_passed=True, audit_passed=True)
        self.assertTrue(allowed)
        self.assertIn("Eligible for auto-merge", reason)

    def test_can_auto_merge_denied_when_needs_approval(self):
        stats = [{"path": ".github/workflows/ci.yml", "additions": 2, "deletions": 0}]
        allowed, reason = classify_pr_risk.can_auto_merge(stats, ci_passed=True, audit_passed=True)
        self.assertFalse(allowed)
        self.assertIn("waiting for César", reason)

    def test_can_auto_merge_denied_when_ci_not_green(self):
        stats = [{"path": "README.md", "additions": 10, "deletions": 2}]
        allowed, reason = classify_pr_risk.can_auto_merge(stats, ci_passed=False, audit_passed=True)
        self.assertFalse(allowed)
        self.assertIn("CI check not green", reason)

    def test_can_auto_merge_denied_when_audit_failed(self):
        stats = [{"path": "README.md", "additions": 10, "deletions": 2}]
        allowed, reason = classify_pr_risk.can_auto_merge(stats, ci_passed=True, audit_passed=False)
        self.assertFalse(allowed)
        self.assertIn("audit did not pass", reason)

    def test_apply_pr_label_command(self):
        from unittest.mock import patch
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            classify_pr_risk.apply_pr_label(41, "low-risk")
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            self.assertIn("gh", cmd)
            self.assertIn("pr", cmd)
            self.assertIn("edit", cmd)
            self.assertIn("41", cmd)
            self.assertIn("--add-label", cmd)
            self.assertIn("low-risk", cmd)
            self.assertIn("--remove-label", cmd)
            self.assertIn("needs-approval", cmd)


if __name__ == "__main__":
    unittest.main()
