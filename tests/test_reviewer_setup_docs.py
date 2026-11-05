import os
import re
import unittest
from pathlib import Path


class TestReviewerSetupDocs(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.setup_doc = self.repo_root / "docs" / "setup.md"
        self.merge_policy_doc = self.repo_root / "docs" / "merge-policy.md"

    def test_setup_doc_exists_and_contains_github_app_registration(self):
        self.assertTrue(self.setup_doc.is_file(), f"Missing {self.setup_doc}")
        content = self.setup_doc.read_text(encoding="utf-8")

        # GitHub App setup instructions
        self.assertIn("Reviewer Agent GitHub App Setup", content)
        self.assertIn("Register GitHub App", content)
        self.assertIn("pull_requests: write", content)
        self.assertIn("contents: read", content)
        self.assertIn("checks: read", content)
        self.assertIn("REVIEWER_GITHUB_TOKEN", content)

    def test_setup_doc_documents_ruleset_and_1_approving_review(self):
        content = self.setup_doc.read_text(encoding="utf-8")

        # 1 Approving review + ci status check on main
        self.assertIn("1 Approving Review", content)
        self.assertIn("required_approving_review_count\": 1", content)
        self.assertIn("Require status checks to pass", content)
        self.assertIn("ci", content)

    def test_merge_policy_documents_ruleset_and_permissions(self):
        self.assertTrue(self.merge_policy_doc.is_file(), f"Missing {self.merge_policy_doc}")
        content = self.merge_policy_doc.read_text(encoding="utf-8")

        self.assertIn("1 approving review", content.lower())
        self.assertIn("ci", content)
        self.assertIn("pull_requests: write", content)
        self.assertIn("contents: read", content)
        self.assertIn("checks: read", content)
        self.assertIn("REVIEWER_GITHUB_TOKEN", content)
        self.assertIn("delete_branch_on_merge=false", content)

    def test_merge_policy_end_to_end_checklist(self):
        content = self.merge_policy_doc.read_text(encoding="utf-8")
        self.assertIn("End-to-End Reviewer Flow Verification Checklist", content)
        self.assertIn("Model Resolution", content)
        self.assertIn("GitHub App Identity", content)
        self.assertIn("Reviewer Secret", content)
        self.assertIn("Branch Protection on `main`", content)
        self.assertIn("Three-Tier Risk Triage", content)
        self.assertIn("Review Loop Guard", content)

    def test_no_secrets_in_repo(self):
        # Ensure dummy or live tokens were not accidentally committed
        content_setup = self.setup_doc.read_text(encoding="utf-8")
        content_merge = self.merge_policy_doc.read_text(encoding="utf-8")

        for forbidden in ["ghp_", "gho_", "github_pat_", "sk-"]:
            self.assertNotIn(forbidden, content_setup)
            self.assertNotIn(forbidden, content_merge)


if __name__ == "__main__":
    unittest.main()
