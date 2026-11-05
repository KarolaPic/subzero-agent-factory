import os
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.score_pr import (
    ScorerConfigError,
    ScorerModelUnavailableError,
    check_scorer_availability,
    format_pr_score_markdown,
    get_configured_scorer_model,
    score_pr_diff,
)


class TestScorePR(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent

    def test_default_scorer_model_is_gemini_flash_low(self):
        model = get_configured_scorer_model()
        self.assertEqual(model, "gemini-3.8-flash-low")

    def test_check_scorer_availability_success(self):
        model = check_scorer_availability("gemini-3.8-flash-low")
        self.assertEqual(model, "gemini-3.8-flash-low")

    def test_check_scorer_availability_halts_on_unavailability(self):
        os.environ["SCORER_MODEL_UNAVAILABLE"] = "1"
        try:
            with self.assertRaises(ScorerModelUnavailableError) as ctx:
                check_scorer_availability("gemini-3.8-flash-low")
            self.assertIn("unavailable", str(ctx.exception).lower())
            self.assertIn("no fallback", str(ctx.exception).lower())
        finally:
            os.environ.pop("SCORER_MODEL_UNAVAILABLE", None)

    def test_forbidden_models_rejected(self):
        for forbidden in ["claude-3-5-sonnet", "gpt-4o", "gemini-4-argon", "openai-o1"]:
            with self.assertRaises(ScorerConfigError):
                check_scorer_availability(forbidden)

    def test_score_pr_diff_clean_slice(self):
        clean_diff = """diff --git a/scripts/feature.py b/scripts/feature.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/scripts/feature.py
@@ -0,0 +1,20 @@
+def feature():
+    return True
diff --git a/tests/test_feature.py b/tests/test_feature.py
new file mode 100644
index 0000000..7654321
--- /dev/null
+++ b/tests/test_feature.py
@@ -0,0 +1,15 @@
+import unittest
+class TestFeature(unittest.TestCase):
+    def test_ok(self):
+        self.assertTrue(True)
"""
        result = score_pr_diff(clean_diff, summary="feat: sample tracer-bullet\n\nCloses #42")
        self.assertGreaterEqual(result["score"], 9.0)
        self.assertEqual(result["model"], "gemini-3.8-flash-low")
        self.assertIn("tracer-bullet", result["reason"].lower())
        self.assertIn("test coverage", result["reason"].lower())

    def test_score_pr_diff_large_and_missing_tests(self):
        # 400 lines without tests
        large_diff = "diff --git a/app.py b/app.py\n" + "\n".join(f"+line {i}" for i in range(400))
        result = score_pr_diff(large_diff, summary="feat: massive diff")
        self.assertLess(result["score"], 8.0)
        self.assertIn("large diff", result["reason"].lower())
        self.assertIn("no new unit tests", result["reason"].lower())

    def test_format_pr_score_markdown(self):
        result = {
            "score": 9.5,
            "reason": "Concise tracer-bullet slice, comprehensive unit test coverage included",
            "model": "gemini-3.8-flash-low",
        }
        md = format_pr_score_markdown(result)
        self.assertIn("- **PR Score**: 9.5/10", md)
        self.assertIn("gemini-3.8-flash-low", md)

    def test_score_pr_cli_check_model(self):
        cmd = [sys.executable, str(self.repo_root / "scripts" / "score_pr.py"), "--check-model"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("valid and available", res.stdout)

    def test_score_pr_cli_unavailable_halt(self):
        cmd = [sys.executable, str(self.repo_root / "scripts" / "score_pr.py"), "--check-model"]
        env = dict(os.environ, SCORER_MODEL_UNAVAILABLE="1")
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)
        self.assertIn("FATAL", res.stderr)
        self.assertIn("unavailable", res.stderr.lower())

    def test_score_pr_cli_base_and_head(self):
        cmd = [sys.executable, str(self.repo_root / "scripts" / "score_pr.py"), "--base", "HEAD~1", "--head", "HEAD", "--json"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn('"score"', res.stdout)
        self.assertIn("gemini-3.8-flash-low", res.stdout)


if __name__ == "__main__":
    unittest.main()
