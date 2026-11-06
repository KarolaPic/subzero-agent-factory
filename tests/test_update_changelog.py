import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.update_changelog import (
    format_entry,
    map_type_to_category,
    update_changelog_content,
    update_changelog_file,
)


class TestUpdateChangelog(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.changelog_path = Path(self.test_dir) / "CHANGELOG.md"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_map_type_to_category(self):
        self.assertEqual(map_type_to_category("feat"), "Added")
        self.assertEqual(map_type_to_category("feature"), "Added")
        self.assertEqual(map_type_to_category("fix"), "Fixed")
        self.assertEqual(map_type_to_category("bugfix"), "Fixed")
        self.assertEqual(map_type_to_category("perf"), "Changed")
        self.assertEqual(map_type_to_category("refactor"), "Changed")
        self.assertEqual(map_type_to_category("security"), "Security")
        self.assertEqual(map_type_to_category("remove"), "Removed")
        self.assertEqual(map_type_to_category("deprecate"), "Deprecated")
        self.assertEqual(map_type_to_category("chore"), "Changed")

    def test_format_entry(self):
        # Entry with both issue and PR
        entry = format_entry(
            summary="support autonomous changelog updates",
            repo_slug="cesarchavezcal/grok-bot-agent-factory",
            issue=122,
            pr=123,
        )
        self.assertEqual(
            entry,
            "- Support autonomous changelog updates "
            "([#122](https://github.com/cesarchavezcal/grok-bot-agent-factory/issues/122), "
            "[#123](https://github.com/cesarchavezcal/grok-bot-agent-factory/pull/123)).",
        )

        # Entry with only issue
        entry_issue = format_entry(
            summary="fix webhook retry timeout",
            repo_slug="test/repo",
            issue="45",
        )
        self.assertEqual(
            entry_issue,
            "- Fix webhook retry timeout ([#45](https://github.com/test/repo/issues/45)).",
        )

    def test_insert_into_existing_category(self):
        content = (
            "# Changelog\n\n"
            "## [Unreleased]\n\n"
            "### Added\n"
            "- Initial entry ([#1](url)).\n\n"
            "## [2026-11-05]\n"
        )
        entry = "- New feature entry ([#122](url))."
        new_content, modified = update_changelog_content(content, entry, category="Added")
        self.assertTrue(modified)
        self.assertIn("### Added\n- New feature entry ([#122](url)).\n- Initial entry ([#1](url)).", new_content)

    def test_create_missing_category_in_unreleased(self):
        content = (
            "# Changelog\n\n"
            "## [Unreleased]\n\n"
            "### Added\n"
            "- Feature one.\n\n"
            "## [2026-11-05]\n"
        )
        entry = "- Bug fix for crash ([#50](url))."
        new_content, modified = update_changelog_content(content, entry, category="Fixed")
        self.assertTrue(modified)
        self.assertIn("### Fixed", new_content)
        self.assertIn("- Bug fix for crash ([#50](url)).", new_content)

    def test_idempotency_avoids_duplicate_entry(self):
        content = (
            "# Changelog\n\n"
            "## [Unreleased]\n\n"
            "### Added\n"
            "- Feature entry ([#122](https://github.com/org/repo/issues/122), [#123](https://github.com/org/repo/pull/123)).\n\n"
            "## [2026-11-05]\n"
        )
        entry = "- Feature entry ([#122](https://github.com/org/repo/issues/122), [#123](https://github.com/org/repo/pull/123))."
        new_content, modified = update_changelog_content(content, entry, category="Added", pr=123, issue=122)
        self.assertFalse(modified)
        self.assertEqual(content, new_content)

    def test_update_changelog_file(self):
        modified = update_changelog_file(
            changelog_path=self.changelog_path,
            summary="install impeccable skill and automate changelog updates",
            category="Added",
            repo_slug="cesarchavezcal/grok-bot-agent-factory",
            issue=122,
            pr=123,
        )
        self.assertTrue(modified)
        content = self.changelog_path.read_text(encoding="utf-8")
        self.assertIn("## [Unreleased]", content)
        self.assertIn("### Added", content)
        self.assertIn("Install impeccable skill and automate changelog updates", content)


if __name__ == "__main__":
    unittest.main()
