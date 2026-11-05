import os
import unittest
import yaml


class TestIssueTemplates(unittest.TestCase):
    def setUp(self):
        self.templates_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".github",
            "ISSUE_TEMPLATE"
        )

    def test_required_files_exist(self):
        expected_files = ["task-card.yml", "bug.yml", "feature.md", "config.yml"]
        for filename in expected_files:
            filepath = os.path.join(self.templates_dir, filename)
            self.assertTrue(os.path.isfile(filepath), f"Missing issue template file: {filename}")

    def test_task_card_yaml_structure(self):
        filepath = os.path.join(self.templates_dir, "task-card.yml")
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("name"), "Task Card")
        self.assertIn("agent", data.get("labels", []))
        self.assertIn("feature", data.get("labels", []))

        body = data.get("body", [])
        self.assertIsInstance(body, list)

        # Extract field IDs and labels
        field_ids = {item.get("id"): item for item in body if isinstance(item, dict) and "id" in item}
        self.assertIn("goal", field_ids, "task-card.yml missing 'goal' field")
        self.assertIn("done-when", field_ids, "task-card.yml missing 'done-when' field")
        self.assertIn("dont-touch", field_ids, "task-card.yml missing 'dont-touch' field")

        # Verify required validations
        self.assertTrue(field_ids["goal"].get("validations", {}).get("required"))
        self.assertTrue(field_ids["done-when"].get("validations", {}).get("required"))
        self.assertTrue(field_ids["dont-touch"].get("validations", {}).get("required"))

        # Verify task list placeholder in done-when
        placeholder = field_ids["done-when"].get("attributes", {}).get("placeholder", "")
        self.assertIn("- [ ]", placeholder)

    def test_bug_report_yaml_structure(self):
        filepath = os.path.join(self.templates_dir, "bug.yml")
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("name"), "Bug Report")
        self.assertIn("bug", data.get("labels", []))
        self.assertIn("agent", data.get("labels", []))

        body = data.get("body", [])
        field_ids = {item.get("id"): item for item in body if isinstance(item, dict) and "id" in item}

        # Preserves repro fields
        self.assertIn("what-happened", field_ids)
        self.assertIn("expected", field_ids)
        self.assertIn("steps", field_ids)

        # Contains Done when and Don't touch
        self.assertIn("done-when", field_ids, "bug.yml missing 'done-when' field")
        self.assertIn("dont-touch", field_ids, "bug.yml missing 'dont-touch' field")
        self.assertTrue(field_ids["done-when"].get("validations", {}).get("required"))
        self.assertTrue(field_ids["dont-touch"].get("validations", {}).get("required"))

    def test_feature_markdown_structure(self):
        filepath = os.path.join(self.templates_dir, "feature.md")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Frontmatter checks
        self.assertTrue(content.startswith("---"))
        self.assertIn('labels: ["feature"]', content)

        # Standard section checks
        self.assertIn("## Goal", content)
        self.assertIn("## Done when", content)
        self.assertIn("## Don't touch", content)
        self.assertIn("- [ ]", content)


if __name__ == "__main__":
    unittest.main()
