"""Unit tests for External Core Factory framework detector and project adapter."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.project_adapter import (
    ProjectAdapter,
    SchemaValidationError,
    detect_framework,
    load_project_adapter,
    validate_adapter_config,
)


class TestProjectAdapter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_detect_nodejs_framework(self):
        """Auto-detects Node.js project from package.json with npm test."""
        (self.project_path / "package.json").write_text('{"name": "mock-node"}', encoding="utf-8")
        info = detect_framework(self.project_path)
        self.assertEqual(info["framework"], "node")
        self.assertEqual(info["verify_command"], "npm test")
        self.assertEqual(info["base_branch"], "main")

    def test_detect_python_framework(self):
        """Auto-detects Python project from pyproject.toml with pytest."""
        (self.project_path / "pyproject.toml").write_text('[project]\nname = "mock-py"', encoding="utf-8")
        info = detect_framework(self.project_path)
        self.assertEqual(info["framework"], "python")
        self.assertEqual(info["verify_command"], "pytest")

    def test_detect_rust_framework(self):
        """Auto-detects Rust project from Cargo.toml with cargo test."""
        (self.project_path / "Cargo.toml").write_text('[package]\nname = "mock-rust"', encoding="utf-8")
        info = detect_framework(self.project_path)
        self.assertEqual(info["framework"], "rust")
        self.assertEqual(info["verify_command"], "cargo test")

    def test_detect_go_framework(self):
        """Auto-detects Go project from go.mod with go test ./..."""
        (self.project_path / "go.mod").write_text("module example.com/mock", encoding="utf-8")
        info = detect_framework(self.project_path)
        self.assertEqual(info["framework"], "go")
        self.assertEqual(info["verify_command"], "go test ./...")

    def test_validate_valid_factory_config(self):
        """Validates correct .factory.yml dictionary against schema."""
        config = {
            "name": "my-service",
            "base_branch": "master",
            "verify_command": "make test",
            "exclude_skills": ["apple-design", "mobile-native"],
            "memory_tier": "dual",
        }
        self.assertTrue(validate_adapter_config(config))

    def test_validate_invalid_factory_config_raises_error(self):
        """Rejects .factory.yml with invalid fields or unknown properties."""
        bad_config = {
            "name": "my-service",
            "unauthorized_key": 123,
        }
        with self.assertRaises(SchemaValidationError):
            validate_adapter_config(bad_config)

        bad_enum = {
            "memory_tier": "invalid-tier",
        }
        with self.assertRaises(SchemaValidationError):
            validate_adapter_config(bad_enum)

    def test_load_project_adapter_with_overrides(self):
        """Loads and merges .factory.yml overrides with project auto-detection."""
        (self.project_path / "package.json").write_text('{"name": "mock-node"}', encoding="utf-8")
        factory_yaml = """
        base_branch: develop
        verify_command: npm run test:ci
        exclude_skills:
          - stageshow
        github_user: custom-bot
        """
        (self.project_path / ".factory.yml").write_text(factory_yaml, encoding="utf-8")

        adapter = load_project_adapter(self.project_path)
        self.assertEqual(adapter.framework, "node")
        self.assertEqual(adapter.base_branch, "develop")
        self.assertEqual(adapter.verify_command, "npm run test:ci")
        self.assertEqual(adapter.exclude_skills, ["stageshow"])
        self.assertEqual(adapter.github_user, "custom-bot")


if __name__ == "__main__":
    unittest.main()
