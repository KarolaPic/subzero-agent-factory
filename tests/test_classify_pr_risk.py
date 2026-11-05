
"""Unit tests for scripts/classify_pr_risk.py.

Verifies diff risk classification rules across the three-tier model:
- low-risk: docs-only, tests-only, small code fix (< 50 lines) with zero high-risk paths.
- normal: standard code changes (>= 50 lines) with zero high-risk paths; routes to reviewer agent.
- high-risk: changes touching auth/secrets, CI/workflows, branch rules/rulesets,
  dependencies, model configs, database migrations, deployment, or control plane (AGENTS.md / skills).
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

# Add repo root to import path so we can import classify_pr_risk directly
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'scripts'))

import classify_pr_risk


class TestClassifyPRRisk(unittest.TestCase):
    def test_empty_diff_is_low_risk(self):
        res = classify_pr_risk.classify_file_stats([])
        self.assertEqual(res['classification'], 'low-risk')
        self.assertEqual(res['risk_tier'], 'low-risk')
        self.assertTrue(res['is_low_risk'])
        self.assertFalse(res['is_normal'])
        self.assertFalse(res['is_high_risk'])
        self.assertEqual(res['total_changed_lines'], 0)

    def test_docs_only_is_low_risk_regardless_of_line_count(self):
        stats = [
            {'path': 'README.md', 'additions': 100, 'deletions': 50},
            {'path': 'docs/merge-policy.md', 'additions': 200, 'deletions': 10},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res['classification'], 'low-risk')
        self.assertEqual(res['risk_tier'], 'low-risk')
        self.assertTrue(res['is_low_risk'])
        self.assertEqual(res['total_changed_lines'], 360)

    def test_tests_only_is_low_risk_regardless_of_line_count(self):
        stats = [
            {'path': 'tests/test_models.py', 'additions': 150, 'deletions': 20},
            {'path': 'tests/test_evaluator.py', 'additions': 80, 'deletions': 40},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res['classification'], 'low-risk')
        self.assertEqual(res['risk_tier'], 'low-risk')
        self.assertTrue(res['is_low_risk'])
        self.assertEqual(res['total_changed_lines'], 290)

    def test_small_code_fix_under_50_lines_is_low_risk(self):
        stats = [
            {'path': 'scripts/evaluator.py', 'additions': 12, 'deletions': 8},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res['classification'], 'low-risk')
        self.assertEqual(res['risk_tier'], 'low-risk')
        self.assertTrue(res['is_low_risk'])
        self.assertEqual(res['total_changed_lines'], 20)

    def test_code_fix_at_50_lines_is_normal_risk(self):
        stats = [
            {'path': 'scripts/evaluator.py', 'additions': 30, 'deletions': 20},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res['classification'], 'normal')
        self.assertEqual(res['risk_tier'], 'normal')
        self.assertTrue(res['is_normal'])
        self.assertFalse(res['is_low_risk'])
        self.assertFalse(res['is_high_risk'])
        self.assertEqual(res['routes_to'], 'reviewer-agent')
        self.assertEqual(res['total_changed_lines'], 50)

    def test_code_fix_exceeding_50_lines_is_normal_risk(self):
        stats = [
            {'path': 'scripts/evaluator.py', 'additions': 45, 'deletions': 15},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res['classification'], 'normal')
        self.assertEqual(res['risk_tier'], 'normal')
        self.assertTrue(res['is_normal'])
        self.assertFalse(res['is_low_risk'])
        self.assertFalse(res['is_high_risk'])
        self.assertEqual(res['routes_to'], 'reviewer-agent')
        self.assertEqual(res['total_changed_lines'], 60)

    def test_mixed_docs_and_code_under_50_lines_is_low_risk(self):
        stats = [
            {'path': 'docs/setup.md', 'additions': 5, 'deletions': 2},
            {'path': 'scripts/evaluator.py', 'additions': 10, 'deletions': 5},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res['classification'], 'low-risk')
        self.assertTrue(res['is_low_risk'])
        self.assertEqual(res['total_changed_lines'], 22)

    def test_mixed_docs_and_code_over_50_lines_is_normal_risk(self):
        stats = [
            {'path': 'docs/setup.md', 'additions': 35, 'deletions': 10},
            {'path': 'scripts/evaluator.py', 'additions': 10, 'deletions': 10},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res['classification'], 'normal')
        self.assertTrue(res['is_normal'])
        self.assertEqual(res['routes_to'], 'reviewer-agent')
        self.assertEqual(res['total_changed_lines'], 65)

    def test_workflow_change_is_high_risk_even_single_line(self):
        stats = [
            {'path': '.github/workflows/ci.yml', 'additions': 1, 'deletions': 1},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res['classification'], 'high-risk')
        self.assertTrue(res['is_high_risk'])
        self.assertTrue(res['requires_cesar'])
        self.assertEqual(res['routes_to'], 'cesar')
        self.assertTrue(any('workflow' in r.lower() for r in res['reasons']))

    def test_model_configuration_change_is_high_risk(self):
        stats = [
            {'path': 'models.yml', 'additions': 1, 'deletions': 1},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res['classification'], 'high-risk')
        self.assertTrue(res['is_high_risk'])
        self.assertTrue(any('model' in r.lower() for r in res['reasons']))

        stats_allowed = [
            {'path': 'models.allowed.yml', 'additions': 2, 'deletions': 0},
        ]
        res_allowed = classify_pr_risk.classify_file_stats(stats_allowed)
        self.assertEqual(res_allowed['classification'], 'high-risk')
        self.assertTrue(res_allowed['is_high_risk'])

    def test_dependency_change_is_high_risk(self):
        dep_files = [
            'package.json',
            'package-lock.json',
            'requirements.txt',
            'pyproject.toml',
            'go.mod',
            'Cargo.toml',
        ]
        for f in dep_files:
            with self.subTest(file=f):
                stats = [{'path': f, 'additions': 1, 'deletions': 0}]
                res = classify_pr_risk.classify_file_stats(stats)
                self.assertEqual(res['classification'], 'high-risk')
                self.assertTrue(res['is_high_risk'])

    def test_auth_and_secrets_are_high_risk(self):
        auth_paths = [
            '.env',
            '.env.production',
            'auth/login.py',
            'secrets/tokens.json',
        ]
        for p in auth_paths:
            with self.subTest(path=p):
                stats = [{'path': p, 'additions': 1, 'deletions': 0}]
                res = classify_pr_risk.classify_file_stats(stats)
                self.assertEqual(res['classification'], 'high-risk')
                self.assertTrue(res['is_high_risk'])
                self.assertTrue(res['requires_cesar'])

    def test_branch_rulesets_are_high_risk(self):
        stats = [{'path': '.github/rulesets/main.json', 'additions': 5, 'deletions': 0}]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res['classification'], 'high-risk')
        self.assertTrue(res['is_high_risk'])
        self.assertTrue(any('ruleset' in r.lower() for r in res['reasons']))

    def test_migrations_and_deletions_are_high_risk(self):
        migration_paths = [
            'migrations/0001_initial.sql',
            'db/migrations/user_table.sql',
        ]
        for m in migration_paths:
            with self.subTest(path=m):
                stats = [{'path': m, 'additions': 10, 'deletions': 2}]
                res = classify_pr_risk.classify_file_stats(stats)
                self.assertEqual(res['classification'], 'high-risk')
                self.assertTrue(res['is_high_risk'])

    def test_deploy_configurations_are_high_risk(self):
        deploy_paths = [
            'deploy/deploy.sh',
            'Dockerfile',
            'docker-compose.yml',
        ]
        for d in deploy_paths:
            with self.subTest(path=d):
                stats = [{'path': d, 'additions': 5, 'deletions': 1}]
                res = classify_pr_risk.classify_file_stats(stats)
                self.assertEqual(res['classification'], 'high-risk')
                self.assertTrue(res['is_high_risk'])

    def test_factory_core_config_is_high_risk(self):
        stats = [
            {'path': '.factory/config.json', 'additions': 1, 'deletions': 1},
        ]
        res = classify_pr_risk.classify_file_stats(stats)
        self.assertEqual(res['classification'], 'high-risk')
        self.assertTrue(res['is_high_risk'])

    def test_skill_evolution_and_agents_md_is_high_risk_adr_0001(self):
        stats_skill = [
            {'path': '.agents/skills/implement-ticket/SKILL.md', 'additions': 2, 'deletions': 1},
        ]
        res_skill = classify_pr_risk.classify_file_stats(stats_skill)
        self.assertEqual(res_skill['classification'], 'high-risk')
        self.assertTrue(res_skill['is_high_risk'])

        stats_agents = [
            {'path': 'AGENTS.md', 'additions': 2, 'deletions': 1},
        ]
        res_agents = classify_pr_risk.classify_file_stats(stats_agents)
        self.assertEqual(res_agents['classification'], 'high-risk')
        self.assertTrue(res_agents['is_high_risk'])

    def test_parse_numstat(self):
        numstat_text = "\n".join(["10\t5\tscripts/evaluator.py", "20\t0\tREADME.md", "-\t-\tbinary_file.png"]) + "\n"
        parsed = classify_pr_risk.parse_numstat(numstat_text)
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0], {"path": "scripts/evaluator.py", "additions": 10, "deletions": 5})
        self.assertEqual(parsed[1], {"path": "README.md", "additions": 20, "deletions": 0})
        self.assertEqual(parsed[2], {"path": "binary_file.png", "additions": 0, "deletions": 0})

    def test_cli_execution_with_numstat_stdin(self):
        numstat_input = "\t".join(["2", "1", "README.md"]) + "\n"
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
        numstat_input = "\t".join(["10", "5", ".github/workflows/ci.yml"]) + "\n"
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "classify_pr_risk.py"), "--stdin", "--label"],
            input=numstat_input,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(proc.stdout.strip(), "high-risk")

    def test_can_auto_merge_success_for_low_risk(self):
        stats = [{'path': 'README.md', 'additions': 10, 'deletions': 2}]
        allowed, reason = classify_pr_risk.can_auto_merge(stats, ci_passed=True, audit_passed=True)
        self.assertTrue(allowed)
        self.assertIn('Eligible for auto-merge', reason)

    def test_can_auto_merge_normal_risk_requires_reviewer(self):
        stats = [{'path': 'scripts/evaluator.py', 'additions': 40, 'deletions': 20}]
        # Without reviewer approval
        allowed, reason = classify_pr_risk.can_auto_merge(stats, ci_passed=True, reviewer_approved=False)
        self.assertFalse(allowed)
        self.assertIn('awaiting reviewer agent approval', reason)

        # With reviewer approval + green CI
        allowed, reason = classify_pr_risk.can_auto_merge(stats, ci_passed=True, reviewer_approved=True)
        self.assertTrue(allowed)
        self.assertIn('Eligible for auto-merge', reason)

    def test_can_auto_merge_denied_when_high_risk(self):
        stats = [{'path': '.github/workflows/ci.yml', 'additions': 2, 'deletions': 0}]
        allowed, reason = classify_pr_risk.can_auto_merge(stats, ci_passed=True, audit_passed=True, reviewer_approved=True)
        self.assertFalse(allowed)
        self.assertIn('waiting for César', reason)

    def test_can_auto_merge_denied_when_ci_not_green(self):
        stats = [{'path': 'README.md', 'additions': 10, 'deletions': 2}]
        allowed, reason = classify_pr_risk.can_auto_merge(stats, ci_passed=False, audit_passed=True)
        self.assertFalse(allowed)
        self.assertIn('CI check not green', reason)

    def test_apply_pr_label_command(self):
        from unittest.mock import patch
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            classify_pr_risk.apply_pr_label(41, 'low-risk')
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            self.assertIn('gh', cmd)
            self.assertIn('pr', cmd)
            self.assertIn('edit', cmd)
            self.assertIn('41', cmd)
            self.assertIn('--add-label', cmd)
            self.assertIn('low-risk', cmd)
            self.assertIn('--remove-label', cmd)


if __name__ == '__main__':
    unittest.main()
