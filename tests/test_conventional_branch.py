import unittest
from scripts.validate_conventions import (
    validate_branch_name,
    validate_commit_message,
    validate_pr_title,
)


class TestConventionalConventions(unittest.TestCase):
    def test_valid_trunk_branches(self):
        for trunk in ["main", "master", "develop"]:
            valid, msg = validate_branch_name(trunk)
            self.assertTrue(valid, f"Expected {trunk} to be valid: {msg}")

    def test_valid_conventional_branch_names(self):
        valid_branches = [
            "feat/94-conventional-branch-standards",
            "feature/user-authentication",
            "fix/12-webhook-duplicate",
            "bugfix/header-rendering-bug",
            "chore/40-wire-run-log",
            "docs/87-changelog-setup",
            "refactor/83-reviewer-pr-body",
            "test/validate-conventions-suite",
            "hotfix/security-patch-v1.2",
            "release/v1.0.0",
            "chore/upgrade-node-v20.11",
            "feat/89-slice",
        ]
        for branch in valid_branches:
            valid, msg = validate_branch_name(branch)
            self.assertTrue(valid, f"Expected {branch} to be valid: {msg}")

    def test_invalid_conventional_branch_names(self):
        invalid_branches = [
            ("", "empty"),
            ("my-feature-branch", "no prefix"),
            ("random/feature", "invalid prefix"),
            ("feat/", "empty description"),
            ("FEAT/uppercase-type", "uppercase type"),
            ("feat/Uppercase-Description", "uppercase description"),
            ("feat/has_underscores_here", "underscores"),
            ("feat/has spaces in branch", "spaces"),
            ("feat/has--consecutive-hyphens", "consecutive hyphens"),
            ("feat/-leading-hyphen", "leading hyphen"),
            ("feat/trailing-hyphen-", "trailing hyphen"),
            ("feat/consecutive..dots", "consecutive dots"),
            ("feat/.leading-dot", "leading dot"),
            ("feat/trailing-dot.", "trailing dot"),
        ]
        for branch, reason in invalid_branches:
            valid, msg = validate_branch_name(branch)
            self.assertFalse(valid, f"Expected '{branch}' to fail ({reason}), but passed: {msg}")

    def test_valid_conventional_commits(self):
        valid_commits = [
            "feat(run-epic): support plain request intake (#89)",
            "fix(scorer): resolve diff score calculation for small fixes (#60)",
            "docs(changelog): chronicle 2026-11-05 factory overhaul (#87)",
            "chore(runs): log run record for issue #89 (PR #92)",
            "refactor(reviewer): record review verdict in PR body (#83)",
            "test(conventions): add tests for conventional branch naming",
            "feat!: breaking changes to branch schema",
            "feat(api)!: breaking api change",
        ]
        for commit in valid_commits:
            valid, msg = validate_commit_message(commit)
            self.assertTrue(valid, f"Expected '{commit}' to be valid: {msg}")

    def test_invalid_conventional_commits(self):
        invalid_commits = [
            ("", "empty message"),
            ("just fixing things", "no type prefix"),
            ("FEAT: uppercase type", "uppercase type"),
            ("unknown(scope): unsupported type", "invalid type"),
            ("feat: a", "description too short"),
        ]
        for commit, reason in invalid_commits:
            valid, msg = validate_commit_message(commit)
            self.assertFalse(valid, f"Expected '{commit}' to fail ({reason}), but passed: {msg}")

    def test_pr_title_validation(self):
        valid_pr = "feat(conventions): adopt conventional branch and commit standards (#94)"
        valid, msg = validate_pr_title(valid_pr)
        self.assertTrue(valid, msg)

        invalid_pr = "Fixed broken tests and stuff"
        valid, msg = validate_pr_title(invalid_pr)
        self.assertFalse(valid, msg)

    def test_ci_workflow_no_direct_interpolation(self):
        import pathlib
        ci_path = pathlib.Path(".github/workflows/ci.yml")
        content = ci_path.read_text(encoding="utf-8")
        
        # Verify step-level env mapping is present
        self.assertIn('HEAD_REF: ${{ github.head_ref }}', content)
        self.assertIn('PR_TITLE: ${{ github.event.pull_request.title }}', content)
        
        # Verify run block does not directly interpolate expressions
        self.assertNotIn('branch "${{ github.head_ref }}"', content)
        self.assertNotIn('pr-title "${{ github.event.pull_request.title }}"', content)
        
        # Verify execution references env vars
        self.assertIn('python3 scripts/validate_conventions.py branch "$HEAD_REF"', content)
        self.assertIn('python3 scripts/validate_conventions.py pr-title "$PR_TITLE"', content)

    def test_pr_title_validation_shell_metacharacters(self):
        import subprocess
        malicious_titles = [
            'feat(ci): test"; echo pwned #',
            'feat(ci): test && touch /tmp/pwned',
            'feat(ci): `id`',
            'feat(ci): $(whoami)',
            'feat(ci): test | cat /etc/passwd',
            'feat(ci): \' || exit 1 || \'',
        ]
        for title in malicious_titles:
            # Test direct function
            valid, msg = validate_pr_title(title)
            # Either valid or invalid, but must not crash
            self.assertIsInstance(valid, bool)
            
            # Test CLI invocation does not execute subcommands
            proc = subprocess.run(
                ["python3", "scripts/validate_conventions.py", "pr-title", title],
                capture_output=True,
                text=True
            )
            # CLI should run and finish cleanly (exit 0 or 1, not crash or execute injected payload)
            self.assertIn(proc.returncode, (0, 1))


if __name__ == "__main__":
    unittest.main()

