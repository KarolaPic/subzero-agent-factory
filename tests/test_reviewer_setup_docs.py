import os
import re
import unittest
from pathlib import Path


class TestReviewerSetupDocs(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.setup_doc = self.repo_root / "docs" / "setup.md"
        self.merge_policy_doc = self.repo_root / "docs" / "merge-policy.md"

    def test_setup_doc_exists_and_describes_reviewer_gate(self):
        self.assertTrue(self.setup_doc.is_file(), f"Missing {self.setup_doc}")
        content = self.setup_doc.read_text(encoding="utf-8")

        # Reviewer Agent section and single-account operation
        self.assertIn("Reviewer Agent Inspection & Merge Gate", content)
        self.assertIn("cesarchavezcal", content)
        self.assertNotIn("REVIEWER_GITHUB_TOKEN", content)
        self.assertNotIn("Register GitHub App", content)

    def test_setup_doc_documents_ruleset_and_zero_required_reviews(self):
        content = self.setup_doc.read_text(encoding="utf-8")

        # 0 Approving reviews + ci status check on main
        self.assertIn("required_pull_request_reviews: null", content)
        self.assertIn("Require status checks to pass", content)
        self.assertIn("ci", content)
        self.assertNotIn("required_approving_review_count\": 1", content)

    def test_merge_policy_documents_ruleset_and_permissions(self):
        self.assertTrue(self.merge_policy_doc.is_file(), f"Missing {self.merge_policy_doc}")
        content = self.merge_policy_doc.read_text(encoding="utf-8")

        self.assertIn("0 required approving reviews", content.lower())
        self.assertIn("ci", content)
        self.assertIn("delete_branch_on_merge=false", content)
        self.assertNotIn("REVIEWER_GITHUB_TOKEN", content)
        self.assertNotIn("GITHUB_APP_TOKEN", content)

    def test_merge_policy_end_to_end_checklist(self):
        content = self.merge_policy_doc.read_text(encoding="utf-8")
        self.assertIn("End-to-End Reviewer Flow Verification Checklist", content)
        self.assertIn("Model Resolution", content)
        self.assertIn("Reviewer Verdict in PR Body", content)
        self.assertIn("Run Log Record", content)
        self.assertIn("Branch Protection on `main`", content)
        self.assertIn("Three-Tier Risk Triage", content)
        self.assertIn("Review Loop Guard", content)
        self.assertNotIn("GitHub App Identity", content)
        self.assertNotIn("Reviewer Secret", content)

    def test_no_secrets_in_repo(self):
        # Ensure dummy or live tokens were not accidentally committed
        content_setup = self.setup_doc.read_text(encoding="utf-8")
        content_merge = self.merge_policy_doc.read_text(encoding="utf-8")

        for forbidden in ["ghp_", "gho_", "github_pat_", "sk-"]:
            self.assertNotIn(forbidden, content_setup)
            self.assertNotIn(forbidden, content_merge)


if __name__ == "__main__":
    unittest.main()
