import os
import unittest


class TestPullRequestTemplate(unittest.TestCase):
    def setUp(self):
        self.template_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".github",
            "PULL_REQUEST_TEMPLATE.md"
        )

    def test_pr_template_exists(self):
        self.assertTrue(os.path.isfile(self.template_path), "Missing .github/PULL_REQUEST_TEMPLATE.md")

    def test_pr_template_required_sections(self):
        with open(self.template_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check required sections
        self.assertIn("## Why", content, "PULL_REQUEST_TEMPLATE.md missing '## Why' section")
        self.assertIn("## What changed", content, "PULL_REQUEST_TEMPLATE.md missing '## What changed' section")
        self.assertIn("## How it was tested", content, "PULL_REQUEST_TEMPLATE.md missing '## How it was tested' section")
        self.assertIn("Closes #", content, "PULL_REQUEST_TEMPLATE.md missing 'Closes #' line")

    def test_pr_template_references_models_yml(self):
        with open(self.template_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Models line read from models.yml
        self.assertIn("models.yml", content)
        self.assertIn("builder", content)
        self.assertIn("auditor", content)

    def test_pr_template_has_runtime_proof_and_audit_verdict(self):
        with open(self.template_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("PASS", content)
        self.assertIn("exitCode", content)

    def test_pr_template_no_legacy_model_table(self):
        with open(self.template_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Must not contain legacy multi-model table
        self.assertNotIn("| Phase | Pool | Model | Artifact / Verdict |", content)
        self.assertNotIn("AGY_FAST", content)
        self.assertNotIn("GROK_WORK", content)

    def test_pr_template_disallows_refs_directive(self):
        with open(self.template_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Directive must disallow Refs # and specify Closes #
        self.assertIn("never use Refs #N", content)
        # Ensure 'Refs #' does not appear outside of the prohibition instruction
        cleaned = content.replace("never use Refs #N", "")
        self.assertNotIn("Refs #", cleaned)


if __name__ == "__main__":
    unittest.main()
