"""Unit tests for External Core Factory dual-tier memory store and evaluator integration."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.memory_store import (
    DEFAULT_GLOBAL_MEMORY_DIR,
    memory_lock,
    record_lesson,
    resolve_memory_dir,
)


class TestDualTierMemory(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.mock_global_dir = self.root / "global_memory"
        self.mock_local_dir = self.root / "local_repo" / ".factory" / "memory"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_global_memory_path_default(self):
        """Global memory defaults to ~/.factory/memory or env override."""
        with patch.dict(os.environ, {"FACTORY_GLOBAL_MEMORY_DIR": str(self.mock_global_dir)}):
            resolved = resolve_memory_dir(tier="global")
            self.assertEqual(resolved, self.mock_global_dir)
            self.assertTrue(resolved.is_dir())

    def test_local_memory_path(self):
        """Local memory resolves to repo-local .factory/memory."""
        mock_repo = self.root / "local_repo"
        mock_repo.mkdir(parents=True, exist_ok=True)
        resolved = resolve_memory_dir(cwd=mock_repo, tier="local")
        self.assertEqual(resolved, mock_repo / ".factory" / "memory")
        self.assertTrue(resolved.is_dir())

    def test_flock_lockfile_created_in_memory_dir(self):
        """Maintains flock lockfile at .memory.lock inside target memory dir."""
        mem_dir = self.mock_global_dir
        mem_dir.mkdir(parents=True, exist_ok=True)

        with memory_lock(mem_dir):
            lock_file = mem_dir / ".memory.lock"
            self.assertTrue(lock_file.exists())

    def test_record_lesson_routes_to_global_tier(self):
        """Records lessons into global memory path by default."""
        with patch.dict(os.environ, {"FACTORY_GLOBAL_MEMORY_DIR": str(self.mock_global_dir)}):
            res = record_lesson(
                work_item_id="109",
                target_skill="implement-ticket",
                failure_class="rubric-violation",
                rubric_violated="Don't touch violated",
                evidence_summary="Modified protected config",
                tier="global",
            )
            self.assertTrue((self.mock_global_dir / "lessons.jsonl").exists())
            self.assertEqual(res["lesson"]["targetSkill"], "implement-ticket")

    def test_record_lesson_routes_to_local_tier(self):
        """Routes lessons to local store when tier is local."""
        self.mock_local_dir.mkdir(parents=True, exist_ok=True)
        res = record_lesson(
            work_item_id="109",
            target_skill="implement-ticket",
            failure_class="scope-creep",
            rubric_violated="Goal violated",
            evidence_summary="Added unnecessary files",
            mem_dir=self.mock_local_dir,
            tier="local",
        )
        self.assertTrue((self.mock_local_dir / "lessons.jsonl").exists())
        self.assertEqual(res["lesson"]["failureClass"], "scope-creep")


if __name__ == "__main__":
    unittest.main()
