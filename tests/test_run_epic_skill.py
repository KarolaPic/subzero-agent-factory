import os
import re
import unittest


class TestRunEpicSkill(unittest.TestCase):
    def setUp(self):
        self.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.skill_path = os.path.join(self.repo_root, ".agents", "skills", "run-epic", "SKILL.md")

    def test_run_epic_skill_exists(self):
        self.assertTrue(os.path.isfile(self.skill_path), f"Missing {self.skill_path}")

    def test_frontmatter(self):
        with open(self.skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        self.assertIsNotNone(match, "Frontmatter missing or invalid")
        frontmatter = match.group(1)
        self.assertIn("name: run-epic", frontmatter)
        self.assertIn("description:", frontmatter)

    def test_intake_and_sub_issue_discovery(self):
        with open(self.skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Part of #", content)
        self.assertIn("plan-epic", content)
        self.assertIn("Goal", content)
        self.assertIn("Done when", content)
        self.assertIn("Don't touch", content)

    def test_anti_clash_concurrency_guard(self):
        with open(self.skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("in-progress", content)
        self.assertIn("Anti-Clash", content)
        self.assertIn("open pr", content.lower())

    def test_model_resolution_and_unavailability_gate(self):
        with open(self.skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("models.yml", content)
        self.assertIn("epic_planner", content)
        self.assertIn("planner", content)
        self.assertIn("builder", content)
        self.assertIn("auditor", content)
        self.assertIn("NO fallback", content)

    def test_prohibited_models_invariant(self):
        with open(self.skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check invariant: Zero Argon, Claude, GPT
        self.assertRegex(content, r"(?i)zero (claude|gpt|argon)|strictly (zero|prohibits) (claude|gpt|argon)")

    def test_github_account_rules(self):
        with open(self.skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("cesarchavezcal", content)
        self.assertIn("gh auth switch", content)

    def test_human_stop_and_ask_gates(self):
        with open(self.skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("thread final message", content)
        self.assertIn("NEVER post bot comments", content)

    def test_deploy_and_epic_closing_rules(self):
        with open(self.skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("deploy", content)
        self.assertIn("Closes #<FINAL_SUB_ISSUE>", content)
        self.assertIn("Closes #<EPIC_NUMBER>", content)
        self.assertIn("--delete-branch", content)

    def test_idempotency_and_walkthrough(self):
        with open(self.skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Idempotency", content)
        self.assertIn("Resumability", content)
        self.assertIn("Dry-Run Walkthrough", content)

    def test_agents_md_documentation(self):
        agents_path = os.path.join(self.repo_root, "AGENTS.md")
        self.assertTrue(os.path.isfile(agents_path))
        with open(agents_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("$run-epic", content)
        self.assertIn(".agents/skills/run-epic/SKILL.md", content)
        self.assertIn("plan-epic", content)
        self.assertIn("implement-ticket", content)

    def test_setup_md_documentation(self):
        setup_path = os.path.join(self.repo_root, "docs", "setup.md")
        self.assertTrue(os.path.isfile(setup_path))
        with open(setup_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("$run-epic", content)
        self.assertIn("Anti-Clash", content)
        self.assertIn("Idempotency", content)
        self.assertIn("cesarchavezcal", content)


if __name__ == "__main__":
    unittest.main()
