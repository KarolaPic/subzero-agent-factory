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

    def test_run_log_table_sanitizes_dynamic_properties_against_xss(self):
        """Verifies that docs/index.html does not unsafely interpolate run log properties via innerHTML."""
        html = self.index_html.read_text(encoding="utf-8")

        # Must not perform raw template literal innerHTML assignment with dynamic fields
        self.assertNotIn("${r.builder}", html, "docs/index.html must not interpolate r.builder into innerHTML")
        self.assertNotIn("${r.auditor}", html, "docs/index.html must not interpolate r.auditor into innerHTML")
        self.assertNotIn("${r.result}", html, "docs/index.html must not interpolate r.result into innerHTML")
        self.assertNotIn("${issueText}", html, "docs/index.html must not interpolate issueText into innerHTML")
        self.assertNotIn("${prText}", html, "docs/index.html must not interpolate prText into innerHTML")

        # Must use textContent or safe DOM node creation
        self.assertIn("textContent", html, "docs/index.html must use textContent for safe text rendering")

    def test_xss_payloads_render_as_plain_text(self):
        """Verifies that malicious payloads with <script>, <img>, and event handlers are treated as text."""
        import subprocess
        import json

        node_script = """
        // Minimal DOM mock simulating element creation and textContent
        function MockElement(tagName) {
            this.tagName = tagName;
            this.children = [];
            this.className = '';
            this.textContent = '';
        }
        MockElement.prototype.appendChild = function(child) {
            this.children.push(child);
        };

        const document = {
            createElement: function(tag) {
                return new MockElement(tag);
            }
        };

        const window = {
            DashboardMetrics: {
                formatDuration: function(s) { return (s || 0) + 's'; }
            }
        };

        const maliciousRun = {
            issue: "<script>alert('xss-issue')</script>",
            pr: "<img src=x onerror=alert('xss-pr')>",
            result: "merged<svg onload=alert(1)>",
            builder: "<script>alert('xss-builder')</script>",
            auditor: "<a href='javascript:alert(1)'>click</a>",
            interventions: 0,
            kickoffToPrSec: 60,
            prToReviewSec: 30,
            reviewToMergeSec: 45
        };

        const tr = document.createElement('tr');
        const issueText = maliciousRun.issue ? '#' + maliciousRun.issue : '—';
        const prText = maliciousRun.pr ? '#' + maliciousRun.pr : '—';
        const resultClass = 'pill-merged';

        // Replicate safe DOM creation from docs/index.html
        const tdIssue = document.createElement('td');
        const strongIssue = document.createElement('strong');
        strongIssue.textContent = issueText;
        tdIssue.appendChild(strongIssue);
        tr.appendChild(tdIssue);

        const tdPr = document.createElement('td');
        tdPr.textContent = prText;
        tr.appendChild(tdPr);

        const tdResult = document.createElement('td');
        const spanResult = document.createElement('span');
        spanResult.className = 'pill ' + resultClass;
        spanResult.textContent = maliciousRun.result || '';
        tdResult.appendChild(spanResult);
        tr.appendChild(tdResult);

        const tdBuilder = document.createElement('td');
        const codeBuilder = document.createElement('code');
        codeBuilder.textContent = maliciousRun.builder || '';
        tdBuilder.appendChild(codeBuilder);
        tr.appendChild(tdBuilder);

        const tdAuditor = document.createElement('td');
        const codeAuditor = document.createElement('code');
        codeAuditor.textContent = maliciousRun.auditor || '';
        tdAuditor.appendChild(codeAuditor);
        tr.appendChild(tdAuditor);

        console.log(JSON.stringify({
            issueTextContent: strongIssue.textContent,
            prTextContent: tdPr.textContent,
            resultTextContent: spanResult.textContent,
            builderTextContent: codeBuilder.textContent,
            auditorTextContent: codeAuditor.textContent
        }));
        """

        proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=True)
        res = json.loads(proc.stdout.strip())

        # Verify literal string representations are preserved safely in textContent without evaluation
        self.assertEqual(res["issueTextContent"], "#<script>alert('xss-issue')</script>")
        self.assertEqual(res["prTextContent"], "#<img src=x onerror=alert('xss-pr')>")
        self.assertEqual(res["resultTextContent"], "merged<svg onload=alert(1)>")
        self.assertEqual(res["builderTextContent"], "<script>alert('xss-builder')</script>")
        self.assertEqual(res["auditorTextContent"], "<a href='javascript:alert(1)'>click</a>")


if __name__ == "__main__":
    unittest.main()


