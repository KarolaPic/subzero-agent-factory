import os
import re
import unittest


class TestOrchestrateSkill(unittest.TestCase):
    def setUp(self):
        self.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.skill_path = os.path.join(self.repo_root, ".agents", "skills", "orchestrate", "SKILL.md")

    def test_orchestrate_skill_exists(self):
        self.assertTrue(os.path.isfile(self.skill_path), f"Missing {self.skill_path}")

    def test_frontmatter(self):
        with open(self.skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        self.assertIsNotNone(match, "Frontmatter missing or invalid")
        frontmatter = match.group(1)
        self.assertIn("name: orchestrate", frontmatter)
        self.assertIn("description:", frontmatter)

    def test_routing_matrix_subcommands(self):
        with open(self.skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check all four subcommands / modes are present
        self.assertIn("$orchestrate plan", content)
        self.assertIn("$orchestrate bug", content)
        self.assertIn("$orchestrate code", content)
        self.assertIn("$orchestrate <#N", content)

        # Check delegated underlying skill mappings
        self.assertIn("plan-epic", content)
        self.assertIn("fix-bug", content)
        self.assertIn("implement-ticket", content)
        self.assertIn("run-epic", content)

    def test_backward_compatibility_aliases(self):
        with open(self.skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Backward Compatibility", content)
        self.assertIn("$plan-epic", content)
        self.assertIn("$fix-bug", content)
        self.assertIn("$implement-ticket", content)
        self.assertIn("$run-epic", content)

    def test_agents_md_documentation(self):
        agents_path = os.path.join(self.repo_root, "AGENTS.md")
        self.assertTrue(os.path.isfile(agents_path))
        with open(agents_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("$orchestrate", content)
        self.assertIn(".agents/skills/orchestrate/SKILL.md", content)
        self.assertIn("$orchestrate plan", content)
        self.assertIn("$orchestrate bug", content)
        self.assertIn("$orchestrate code", content)

    def test_readme_md_documentation(self):
        readme_path = os.path.join(self.repo_root, "README.md")
        self.assertTrue(os.path.isfile(readme_path))
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("$orchestrate", content)
        self.assertIn(".agents/skills/orchestrate/SKILL.md", content)


if __name__ == "__main__":
    unittest.main()
