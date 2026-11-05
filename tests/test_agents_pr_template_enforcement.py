import os
import unittest


class TestAgentsPRTemplateEnforcement(unittest.TestCase):
    def setUp(self):
        self.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.agents_path = os.path.join(self.repo_root, "AGENTS.md")
        self.implement_ticket_path = os.path.join(
            self.repo_root, ".agents", "skills", "implement-ticket", "SKILL.md"
        )
        self.fix_bug_path = os.path.join(
            self.repo_root, ".agents", "skills", "fix-bug", "SKILL.md"
        )
        self.pr_skill_path = os.path.join(
            self.repo_root, ".agents", "skills", "pr", "SKILL.md"
        )

    def test_agents_md_enforces_short_pr_template(self):
        with open(self.agents_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Must mandate 4 sections in section 5
        self.assertIn("## Why", content)
        self.assertIn("## What changed", content)
        self.assertIn("## How it was tested", content)
        self.assertIn("models.yml", content)
        self.assertIn("Closes #", content)

    def test_implement_ticket_skill_mandates_pr_template(self):
        with open(self.implement_ticket_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("PULL_REQUEST_TEMPLATE.md", content)
        self.assertIn("Why", content)
        self.assertIn("What changed", content)
        self.assertIn("How it was tested", content)

    def test_fix_bug_skill_mandates_pr_template(self):
        with open(self.fix_bug_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("PULL_REQUEST_TEMPLATE.md", content)
        self.assertIn("Why", content)
        self.assertIn("What changed", content)
        self.assertIn("How it was tested", content)

    def test_pr_skill_matches_four_sections(self):
        with open(self.pr_skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("## Why", content)
        self.assertIn("## What changed", content)
        self.assertIn("## How it was tested", content)
        self.assertIn("Closes #", content)


if __name__ == "__main__":
    unittest.main()
