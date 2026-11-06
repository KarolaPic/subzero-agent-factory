"""Unit tests for External Core Factory layered skills resolver and worktree overlay."""

import os
import tempfile
import unittest
from pathlib import Path

from scripts.skills_resolver import clean_skills_overlay, resolve_skills_overlay


class TestSkillsResolver(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        # Mock Global Skills directory
        self.global_skills_dir = self.root / "global_skills"
        self.global_skills_dir.mkdir(parents=True)
        for skill in ("poteto-mode", "tdd", "implement-ticket", "apple-design", "stageshow"):
            s_dir = self.global_skills_dir / skill
            s_dir.mkdir()
            (s_dir / "SKILL.md").write_text(f"# Global {skill}\n", encoding="utf-8")

        # Mock Worktree project
        self.worktree_dir = self.root / "worktree"
        self.worktree_dir.mkdir(parents=True)
        self.local_skills_dir = self.worktree_dir / ".agents" / "skills"
        self.local_skills_dir.mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_symlinks_global_skills_into_worktree(self):
        """Symlinks global core skills into worktree's .agents/skills/."""
        summary = resolve_skills_overlay(
            global_skills_dir=self.global_skills_dir,
            target_worktree=self.worktree_dir,
        )

        for skill in ("poteto-mode", "tdd", "implement-ticket", "apple-design", "stageshow"):
            target_skill = self.local_skills_dir / skill
            self.assertTrue(target_skill.exists())
            self.assertTrue(target_skill.is_symlink())
            self.assertEqual(summary[skill], "global_symlink")

    def test_preserves_local_skills_on_name_collision(self):
        """Preserves project-local skills when name collision occurs with global core skill."""
        # Create a local skill with the same name
        local_tdd = self.local_skills_dir / "tdd"
        local_tdd.mkdir()
        (local_tdd / "SKILL.md").write_text("# Project Custom TDD\n", encoding="utf-8")

        summary = resolve_skills_overlay(
            global_skills_dir=self.global_skills_dir,
            target_worktree=self.worktree_dir,
        )

        # Local tdd must still exist and must NOT be replaced with a symlink
        self.assertTrue(local_tdd.exists())
        self.assertFalse(local_tdd.is_symlink())
        self.assertEqual((local_tdd / "SKILL.md").read_text(encoding="utf-8"), "# Project Custom TDD\n")
        self.assertEqual(summary["tdd"], "local_preserved")

    def test_filters_out_excluded_skills(self):
        """Filters out skills specified in exclude_skills list."""
        summary = resolve_skills_overlay(
            global_skills_dir=self.global_skills_dir,
            target_worktree=self.worktree_dir,
            exclude_skills=["stageshow", "apple-design"],
        )

        self.assertFalse((self.local_skills_dir / "stageshow").exists())
        self.assertFalse((self.local_skills_dir / "apple-design").exists())
        self.assertEqual(summary["stageshow"], "excluded")
        self.assertEqual(summary["apple-design"], "excluded")

        # Non-excluded skills are linked
        self.assertTrue((self.local_skills_dir / "poteto-mode").is_symlink())

    def test_clean_skills_overlay_removes_only_symlinks(self):
        """Cleans up only symlinks, leaving genuine project-local skills untouched."""
        local_custom = self.local_skills_dir / "custom-domain"
        local_custom.mkdir()
        (local_custom / "SKILL.md").write_text("# Custom\n", encoding="utf-8")

        resolve_skills_overlay(
            global_skills_dir=self.global_skills_dir,
            target_worktree=self.worktree_dir,
        )

        # Run clean overlay
        cleaned = clean_skills_overlay(self.worktree_dir)
        self.assertGreater(cleaned, 0)

        # Symlinks are gone
        self.assertFalse((self.local_skills_dir / "poteto-mode").exists())

        # Local skill is untouched
        self.assertTrue(local_custom.exists())
        self.assertFalse(local_custom.is_symlink())


if __name__ == "__main__":
    unittest.main()
