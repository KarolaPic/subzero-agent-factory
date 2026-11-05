"""Unit tests for the GitHub Pages dashboard and deployment documentation."""

import unittest
from pathlib import Path


class TestDashboardPage(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).parent.parent
        self.docs_dir = self.repo_root / "docs"
        self.index_html = self.docs_dir / "index.html"
        self.metrics_js = self.docs_dir / "metrics.js"
        self.setup_docs = self.docs_dir / "pages-setup.md"

    def test_metrics_script_exists(self):
        self.assertTrue(self.metrics_js.exists(), "docs/metrics.js must exist")

    def test_index_html_structure_and_metrics(self):
        self.assertTrue(self.index_html.exists(), "docs/index.html must exist")
        html = self.index_html.read_text(encoding="utf-8")

        # Must be static HTML with no build requirements
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("metrics.js", html)

        # Must declare elements/containers for all required metrics:
        # PRs opened and merged, kickoff -> PR time, PR -> first review, review -> merge, human interventions
        required_indicators = [
            "prs-opened",
            "prs-merged",
            "kickoff-to-pr",
            "pr-to-review",
            "review-to-merge",
            "human-interventions",
        ]
        for indicator in required_indicators:
            self.assertIn(indicator, html, f"docs/index.html must contain indicator element '{indicator}'")

    def test_pages_setup_documentation(self):
        self.assertTrue(self.setup_docs.exists(), "docs/pages-setup.md must exist")
        docs_content = self.setup_docs.read_text(encoding="utf-8")

        # Must mention docs/ directory deployment
        self.assertIn("/docs", docs_content)
        self.assertIn("main", docs_content)

        # Must explicitly mention that César does this by hand
        self.assertTrue(
            "César does this by hand" in docs_content or "César turns on Pages in repo settings by hand" in docs_content or "by hand" in docs_content,
            "docs/pages-setup.md must document that César turns on Pages in repo settings by hand",
        )

    def test_no_secrets_in_docs(self):
        for path in self.docs_dir.glob("*"):
            if path.is_file():
                content = path.read_text(encoding="utf-8", errors="ignore")
                for secret_kw in ["ghp_", "github_pat_", "sk-ant-", "xai-"]:
                    self.assertNotIn(secret_kw, content, f"Possible secret token '{secret_kw}' found in {path.name}")


if __name__ == "__main__":
    unittest.main()
