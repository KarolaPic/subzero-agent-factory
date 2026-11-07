"""Tests for scripts/scaffold_project.py project scaffolding engine."""

from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from scripts.project_adapter import validate_adapter_config
from scripts.scaffold_project import (
    FRAMEWORK_TEMPLATES,
    generate_factory_config,
    install_project_skills,
    scaffold_framework_project,
)


class TestScaffoldProject(unittest.TestCase):
    def test_framework_templates_defined(self):
        """Verify supported frameworks have defined commands."""
        self.assertIn("nextjs", FRAMEWORK_TEMPLATES)
        self.assertIn("expo", FRAMEWORK_TEMPLATES)
        self.assertIn("vite", FRAMEWORK_TEMPLATES)
        self.assertIn("python", FRAMEWORK_TEMPLATES)
        self.assertIn("rust", FRAMEWORK_TEMPLATES)
        self.assertIn("go", FRAMEWORK_TEMPLATES)

    def test_generate_factory_config(self):
        """Verify generated .factory.yml config dictionary matches schema."""
        cfg = generate_factory_config(
            project_name="verce-mvp",
            framework="nextjs",
            verify_command="npm test",
            package_manager="npm",
            build_command="npm run build",
            exclude_skills=["apple-design"],
        )

        self.assertEqual(cfg["name"], "verce-mvp")
        self.assertEqual(cfg["framework"], "node")
        self.assertEqual(cfg["verify_command"], "npm test")
        self.assertEqual(cfg["build_command"], "npm run build")
        self.assertEqual(cfg["package_manager"], "npm")
        self.assertEqual(cfg["exclude_skills"], ["apple-design"])

        # Validate against actual schema
        self.assertTrue(validate_adapter_config(cfg))

    @patch("subprocess.run")
    def test_install_project_skills_success(self, mock_run):
        """Verify install_project_skills executes npx skills add in target dir."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_dir = Path(tmp_dir) / "test-project"
            target_dir.mkdir()

            mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")

            res = install_project_skills(target_dir, dry_run=False)

            self.assertTrue(res["success"])
            self.assertIn("find-skills", res["installed"])
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            self.assertIn("npx", call_args)
            self.assertIn("skills", call_args)
            self.assertIn("find-skills", call_args)

    @patch("subprocess.run")
    def test_install_project_skills_dry_run(self, mock_run):
        """Verify dry_run skips execution."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_dir = Path(tmp_dir) / "test-project"
            target_dir.mkdir()

            res = install_project_skills(target_dir, dry_run=True)

            self.assertTrue(res["success"])
            mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_scaffold_framework_project_runs_cli(self, mock_run):
        """Verify scaffold_framework_project invokes the CLI command and writes .factory.yml."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "projects"
            out_dir.mkdir()

            mock_run.return_value = MagicMock(returncode=0, stdout="Created", stderr="")

            result = scaffold_framework_project(
                project_name="my-app",
                framework="nextjs",
                destination_parent=out_dir,
                dry_run=False,
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["project_name"], "my-app")
            project_path = Path(result["project_path"])
            self.assertTrue(project_path.exists())
            self.assertTrue((project_path / ".factory.yml").is_file())


if __name__ == "__main__":
    unittest.main()
