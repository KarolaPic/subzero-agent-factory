"""Unit tests for fallback skill pinning in scripts/init.sh against supply-chain tampering."""

import json
import re
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
INIT_SCRIPT = ROOT_DIR / "scripts" / "init.sh"
SKILLS_LOCK = ROOT_DIR / "skills-lock.json"


class TestInitSkillsPinning(unittest.TestCase):
    def setUp(self):
        self.assertTrue(INIT_SCRIPT.exists(), "scripts/init.sh must exist")
        self.assertTrue(SKILLS_LOCK.exists(), "skills-lock.json must exist")
        with open(SKILLS_LOCK, "r", encoding="utf-8") as f:
            self.lock_data = json.load(f)

    def test_fallback_installation_pins_immutable_commit_shas(self):
        """Verify scripts/init.sh does not use floating branch heads (main) or unpinned repositories in fallback."""
        init_content = INIT_SCRIPT.read_text(encoding="utf-8")

        # Must not contain unpinned repository references or floating branches in install_official_skills_fallback
        self.assertNotIn(
            "npx -y skills add mattpocock/skills --skill",
            init_content,
            "scripts/init.sh must not use unpinned mattpocock/skills without commit SHA",
        )
        self.assertNotIn(
            "cursor/plugins/tree/main/pstack",
            init_content,
            "scripts/init.sh must not use floating branch tree/main for cursor/plugins",
        )

        # Must pin exact SHAs matching skills-lock.json
        mattpocock_sha = self.lock_data["skills"]["domain-modeling"]["ref"]
        cursor_sha = self.lock_data["skills"]["poteto-mode"]["ref"]
        grill_with_docs_sha = self.lock_data["skills"]["grill-with-docs"]["ref"]

        self.assertTrue(
            re.search(rf"mattpocock/skills/tree/{mattpocock_sha}", init_content),
            f"scripts/init.sh must pin mattpocock/skills to {mattpocock_sha}",
        )
        self.assertTrue(
            re.search(rf"cursor/plugins/tree/{cursor_sha}/pstack", init_content),
            f"scripts/init.sh must pin cursor/plugins to {cursor_sha}",
        )
        self.assertTrue(
            re.search(rf"mattpocock/skills/tree/{grill_with_docs_sha}", init_content),
            f"scripts/init.sh must pin grill-with-docs to {grill_with_docs_sha}",
        )


if __name__ == "__main__":
    unittest.main()
