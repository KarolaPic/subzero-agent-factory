import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SYNC_SCRIPT = os.path.join(ROOT_DIR, "scripts", "sync-template.sh")


class TestSyncTemplate(unittest.TestCase):
    def test_help(self):
        res = subprocess.run([SYNC_SCRIPT, "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("--target", res.stdout)
        self.assertIn("--dry-run", res.stdout)
        self.assertIn("--no-push", res.stdout)

    def test_unknown_argument(self):
        res = subprocess.run([SYNC_SCRIPT, "--unsupported-option"], capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Unknown argument", res.stderr)

    def test_target_missing_path(self):
        res = subprocess.run([SYNC_SCRIPT, "--target"], capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("--target requires a directory path", res.stderr)

    def test_dirty_working_tree_rejected(self):
        with tempfile.TemporaryDirectory() as target_dir:
            subprocess.run(["git", "init", target_dir], check=True, capture_output=True)
            subprocess.run(["git", "-C", target_dir, "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", target_dir, "config", "user.name", "Tester"], check=True)
            
            # Initial commit
            readme = os.path.join(target_dir, "README.md")
            with open(readme, "w") as f:
                f.write("# Target Project\n")
            subprocess.run(["git", "-C", target_dir, "add", "README.md"], check=True)
            subprocess.run(["git", "-C", target_dir, "commit", "-m", "init"], check=True, capture_output=True)

            # Create uncommitted change
            with open(readme, "a") as f:
                f.write("Uncommitted change\n")

            res = subprocess.run(
                [SYNC_SCRIPT, "--source-dir", ROOT_DIR, "--target", target_dir, "--dry-run"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("uncommitted changes", res.stderr)

    def test_dry_run_reverts_cleanly(self):
        with tempfile.TemporaryDirectory() as target_dir:
            subprocess.run(["git", "init", target_dir], check=True, capture_output=True)
            subprocess.run(["git", "-C", target_dir, "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", target_dir, "config", "user.name", "Tester"], check=True)

            readme = os.path.join(target_dir, "README.md")
            with open(readme, "w") as f:
                f.write("# Target Project\n")
            subprocess.run(["git", "-C", target_dir, "add", "README.md"], check=True)
            subprocess.run(["git", "-C", target_dir, "commit", "-m", "init"], check=True, capture_output=True)

            res = subprocess.run(
                [SYNC_SCRIPT, "--source-dir", ROOT_DIR, "--target", target_dir, "--dry-run"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"dry-run failed: {res.stderr}\n{res.stdout}")
            self.assertIn("Dry run complete", res.stdout)

            # Confirm working tree has zero uncommitted or untracked changes
            status = subprocess.run(
                ["git", "-C", target_dir, "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(status.stdout.strip(), "")

    def test_first_time_sync_and_preservation(self):
        with tempfile.TemporaryDirectory() as target_dir:
            subprocess.run(["git", "init", target_dir], check=True, capture_output=True)
            subprocess.run(["git", "-C", target_dir, "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", target_dir, "config", "user.name", "Tester"], check=True)

            # Pre-existing local files that must be preserved
            custom_models_content = "builder: custom-model-override\nauditor: grok-4.7\n"
            models_path = os.path.join(target_dir, "models.yml")
            with open(models_path, "w") as f:
                f.write(custom_models_content)

            os.makedirs(os.path.join(target_dir, ".factory"), exist_ok=True)
            custom_config = {"app": "derived-target-app", "baseBranch": "main"}
            config_path = os.path.join(target_dir, ".factory", "config.json")
            with open(config_path, "w") as f:
                json.dump(custom_config, f)

            subprocess.run(["git", "-C", target_dir, "add", "."], check=True)
            subprocess.run(["git", "-C", target_dir, "commit", "-m", "base setup"], check=True, capture_output=True)

            # 1. Run sync
            res = subprocess.run(
                [SYNC_SCRIPT, "--source-dir", ROOT_DIR, "--target", target_dir, "--no-push"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"sync failed: {res.stderr}\n{res.stdout}")
            self.assertIn("Template sync complete locally", res.stdout)

            # 2. Check manifest and version files
            target_manifest = os.path.join(target_dir, ".factory", "template-sync.json")
            self.assertTrue(os.path.exists(target_manifest), "Target must have .factory/template-sync.json")

            target_version = os.path.join(target_dir, ".factory", "template-version")
            self.assertTrue(os.path.exists(target_version), "Target must have .factory/template-version")
            with open(target_version) as f:
                sha = f.read().strip()
            self.assertEqual(len(sha), 40, f"Expected 40-char SHA, got: {sha}")

            # 3. Check managed paths copied
            self.assertTrue(os.path.exists(os.path.join(target_dir, "models.allowed.yml")))
            self.assertTrue(os.path.exists(os.path.join(target_dir, "scripts", "init.sh")))
            self.assertTrue(os.path.exists(os.path.join(target_dir, ".github", "workflows", "ci.yml")))

            # 4. Check preserved paths were NOT overwritten
            with open(models_path) as f:
                self.assertEqual(f.read(), custom_models_content)

            with open(config_path) as f:
                self.assertEqual(json.load(f), custom_config)

            # 5. Idempotency: re-running on synced state yields zero diff and exits cleanly
            res2 = subprocess.run(
                [SYNC_SCRIPT, "--source-dir", ROOT_DIR, "--target", target_dir, "--no-push"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res2.returncode, 0)
            self.assertIn("All managed files are already up to date", res2.stdout)

    def test_no_eval_in_sync_template_script(self):
        with open(SYNC_SCRIPT, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn('eval "$(', content)
        self.assertNotIn("eval '", content)

    def test_malicious_config_subshell_not_executed(self):
        with tempfile.TemporaryDirectory() as target_dir:
            subprocess.run(["git", "init", target_dir], check=True, capture_output=True)
            subprocess.run(["git", "-C", target_dir, "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", target_dir, "config", "user.name", "Tester"], check=True)

            os.makedirs(os.path.join(target_dir, ".factory"), exist_ok=True)
            marker_file = os.path.join(target_dir, "pwned_marker.txt")
            if os.path.exists(marker_file):
                os.remove(marker_file)

            malicious_config = {
                "app": "evil-app",
                "baseBranch": f"main$(touch {marker_file})"
            }
            with open(os.path.join(target_dir, ".factory", "config.json"), "w") as f:
                json.dump(malicious_config, f)

            readme = os.path.join(target_dir, "README.md")
            with open(readme, "w") as f:
                f.write("# Target\n")
            subprocess.run(["git", "-C", target_dir, "add", "."], check=True)
            subprocess.run(["git", "-C", target_dir, "commit", "-m", "init"], check=True, capture_output=True)

            res = subprocess.run(
                [SYNC_SCRIPT, "--source-dir", ROOT_DIR, "--target", target_dir, "--dry-run"],
                capture_output=True,
                text=True,
            )
            # The marker file must NOT be created by subshell injection
            self.assertFalse(os.path.exists(marker_file), "Malicious command was executed via subshell injection!")


if __name__ == "__main__":
    unittest.main()

