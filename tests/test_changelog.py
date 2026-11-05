import os
import unittest


class TestChangelog(unittest.TestCase):
    def setUp(self):
        self.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.changelog_path = os.path.join(self.repo_root, "CHANGELOG.md")
        self.agents_path = os.path.join(self.repo_root, "AGENTS.md")

    def test_changelog_file_exists(self):
        self.assertTrue(
            os.path.isfile(self.changelog_path),
            f"Missing CHANGELOG.md at {self.changelog_path}",
        )

    def test_changelog_keep_a_changelog_structure(self):
        with open(self.changelog_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("# Changelog", content)
        self.assertIn("Keep a Changelog", content)
        self.assertIn("Semantic Versioning", content)
        self.assertIn("## [Unreleased]", content)
        self.assertIn("## [2026-11-05]", content)

    def test_changelog_documents_key_subsystems(self):
        with open(self.changelog_path, "r", encoding="utf-8") as f:
            content = f.read()

        expected_sections = [
            "Task Card Ingestion & Validation",
            "Run Log System & Audit Trail",
            "Three-Tier Risk Merge Policy & PR Classifier",
            "Autonomous Epic Runner",
            "PR Template Standardization",
            "T3 PR Scorer",
            "Factory Analytics Dashboard",
            "Autonomous PR Reviewer Agent",
            "Design, Motion & Animation Skills Integration",
        ]
        for section in expected_sections:
            self.assertIn(section, content, f"Missing expected subsystem section: {section}")

    def test_agents_md_documents_changelog_rule(self):
        with open(self.agents_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Changelog Maintenance Rule", content)
        self.assertIn("CHANGELOG.md", content)


if __name__ == "__main__":
    unittest.main()
