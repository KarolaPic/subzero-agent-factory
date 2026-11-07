"""Integration tests for scaffold wizard orchestrator routing and skill definitions."""

from __future__ import annotations

from pathlib import Path
import unittest

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestScaffoldOrchestrator(unittest.TestCase):
    def test_scaffold_skill_definition_exists(self):
        """Verify .agents/skills/scaffold-project/SKILL.md exists with required sections."""
        skill_path = ROOT_DIR / ".agents" / "skills" / "scaffold-project" / "SKILL.md"
        self.assertTrue(skill_path.is_file(), "scaffold-project/SKILL.md must exist")
        content = skill_path.read_text(encoding="utf-8")
        self.assertIn("name: scaffold-project", content)
        self.assertIn("$orchestrate new", content)
        self.assertIn("find-skills", content)

    def test_orchestrate_routing_matrix_includes_new(self):
        """Verify .agents/skills/orchestrate/SKILL.md documents $orchestrate new."""
        orch_path = ROOT_DIR / ".agents" / "skills" / "orchestrate" / "SKILL.md"
        self.assertTrue(orch_path.is_file())
        content = orch_path.read_text(encoding="utf-8")
        self.assertIn("$orchestrate new", content)
        self.assertIn("scaffold-project", content)

    def test_readme_and_guide_document_scaffold(self):
        """Verify README.md and docs/external-factory-guide.md contain wizard references."""
        readme = (ROOT_DIR / "README.md").read_text(encoding="utf-8")
        self.assertIn("$orchestrate new", readme)

        guide = (ROOT_DIR / "docs" / "external-factory-guide.md").read_text(encoding="utf-8")
        self.assertIn("$orchestrate new", guide)
        self.assertIn("scaffold_project.py", guide)


if __name__ == "__main__":
    unittest.main()
