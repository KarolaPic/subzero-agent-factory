import os
import subprocess
import tempfile
import unittest
import yaml

from scripts.validate_models import (
    REQUIRED_ROLES,
    FORBIDDEN_PATTERNS,
    validate_models,
    get_allowed_models,
)

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODELS_FILE = os.path.join(ROOT_DIR, "models.yml")
ALLOWED_FILE = os.path.join(ROOT_DIR, "models.allowed.yml")
SETUP_SCRIPT = os.path.join(ROOT_DIR, "scripts", "setup-models.sh")


class TestModelsConfig(unittest.TestCase):
    def test_allowed_models_file_exists_and_valid(self):
        self.assertTrue(os.path.exists(ALLOWED_FILE), "models.allowed.yml must exist")
        allowed = get_allowed_models(ALLOWED_FILE)
        self.assertIn("gemini-3.8-flash-high", allowed)
        self.assertIn("gemini-3.8-flash-medium", allowed)
        self.assertIn("gemini-3.8-flash-low", allowed)
        self.assertIn("grok-4.7", allowed)

        for model in allowed:
            for forbidden in FORBIDDEN_PATTERNS:
                self.assertNotIn(
                    forbidden,
                    model.lower(),
                    f"Forbidden pattern '{forbidden}' found in allowed model '{model}'",
                )

    def test_default_models_yml_valid(self):
        self.assertTrue(os.path.exists(MODELS_FILE), "models.yml must exist")
        data = validate_models(MODELS_FILE, ALLOWED_FILE)
        for role in REQUIRED_ROLES:
            self.assertIn(role, data)
        self.assertEqual(data["builder"], "gemini-3.8-flash-high")
        self.assertEqual(data["auditor"], "grok-4.7")
        self.assertEqual(data["planner"], "gemini-3.8-flash-high")
        self.assertEqual(data["epic_planner"], "gemini-3.8-flash-high")
        self.assertEqual(data["subagents"], "gemini-3.8-flash-high")
        self.assertEqual(data["scorer"], "gemini-3.8-flash-low")
        self.assertNotEqual(data["builder"], data["auditor"])

    def test_validation_rejects_auditor_equal_builder(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as f:
            yaml.dump(
                {
                    "builder": "grok-4.7",
                    "auditor": "grok-4.7",
                    "planner": "grok-4.7",
                    "epic_planner": "grok-4.7",
                    "subagents": "grok-4.7",
                    "scorer": "gemini-3.8-flash-low",
                },
                f,
            )
            temp_path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                validate_models(temp_path, ALLOWED_FILE)
            self.assertIn("Auditor model", str(ctx.exception))
            self.assertIn("must differ from builder", str(ctx.exception))
        finally:
            os.remove(temp_path)

    def test_validation_rejects_unauthorized_model(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as f:
            yaml.dump(
                {
                    "builder": "unauthorized-custom-model",
                    "auditor": "grok-4.7",
                    "planner": "gemini-3.8-flash-high",
                    "epic_planner": "gemini-3.8-flash-high",
                    "subagents": "gemini-3.8-flash-high",
                    "scorer": "gemini-3.8-flash-low",
                },
                f,
            )
            temp_path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                validate_models(temp_path, ALLOWED_FILE)
            self.assertIn("unauthorized model", str(ctx.exception).lower())
        finally:
            os.remove(temp_path)

    def test_validation_rejects_unauthorized_scorer_model(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as f:
            yaml.dump(
                {
                    "builder": "gemini-3.8-flash-high",
                    "auditor": "grok-4.7",
                    "planner": "gemini-3.8-flash-high",
                    "epic_planner": "gemini-3.8-flash-high",
                    "subagents": "gemini-3.8-flash-high",
                    "scorer": "claude-3-opus",
                },
                f,
            )
            temp_path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                validate_models(temp_path, ALLOWED_FILE)
            err = str(ctx.exception).lower()
            self.assertTrue("forbidden model" in err or "unauthorized model" in err)
        finally:
            os.remove(temp_path)

    def test_validation_rejects_missing_role(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as f:
            yaml.dump(
                {
                    "builder": "gemini-3.8-flash-high",
                    "auditor": "grok-4.7",
                    # missing planner, epic_planner, subagents, scorer
                },
                f,
            )
            temp_path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                validate_models(temp_path, ALLOWED_FILE)
            self.assertIn("Missing required role", str(ctx.exception))
        finally:
            os.remove(temp_path)

    def test_setup_script_cli(self):
        # 1. Defaults flag works
        res = subprocess.run([SETUP_SCRIPT, "--defaults"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"setup-models.sh --defaults failed: {res.stderr}")
        data = validate_models(MODELS_FILE, ALLOWED_FILE)
        self.assertEqual(data["builder"], "gemini-3.8-flash-high")
        self.assertEqual(data["auditor"], "grok-4.7")
        self.assertEqual(data["scorer"], "gemini-3.8-flash-low")

        # 2. Reject auditor == builder
        res = subprocess.run(
            [SETUP_SCRIPT, "--builder", "grok-4.7", "--auditor", "grok-4.7"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("must differ from builder", res.stderr + res.stdout)

        # 3. Reject invalid model
        res = subprocess.run(
            [SETUP_SCRIPT, "--builder", "gpt-4o", "--auditor", "grok-4.7"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("not in allowed models list", res.stderr + res.stdout)

        # Reject invalid scorer model
        res = subprocess.run(
            [SETUP_SCRIPT, "--builder", "gemini-3.8-flash-high", "--auditor", "grok-4.7", "--scorer", "gpt-4o"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("not in allowed models list", res.stderr + res.stdout)

        # 4. Custom valid models setup
        res = subprocess.run(
            [SETUP_SCRIPT, "--builder", "gemini-3.8-flash-low", "--auditor", "grok-4.7", "--scorer", "gemini-3.8-flash-medium"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        custom_data = validate_models(MODELS_FILE, ALLOWED_FILE)
        self.assertEqual(custom_data["builder"], "gemini-3.8-flash-low")
        self.assertEqual(custom_data["auditor"], "grok-4.7")
        self.assertEqual(custom_data["planner"], "gemini-3.8-flash-low")
        self.assertEqual(custom_data["epic_planner"], "gemini-3.8-flash-low")
        self.assertEqual(custom_data["subagents"], "gemini-3.8-flash-low")
        self.assertEqual(custom_data["scorer"], "gemini-3.8-flash-medium")

        # Reset back to template defaults
        subprocess.run([SETUP_SCRIPT, "--defaults"], check=True)

    def test_setup_script_interactive(self):
        import pty
        master, slave = pty.openpty()
        proc = subprocess.Popen(
            [SETUP_SCRIPT],
            stdin=slave,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
        )
        os.close(slave)
        # Choice 1 for builder (gemini-3.8-flash-low), choice 4 for auditor (grok-4.7), Y for all roles
        os.write(master, b"1\n4\nY\n")
        stdout, stderr = proc.communicate()
        os.close(master)
        self.assertEqual(proc.returncode, 0, f"Interactive setup failed: {stderr.decode()}")
        data = validate_models(MODELS_FILE, ALLOWED_FILE)
        self.assertEqual(data["builder"], "gemini-3.8-flash-low")
        self.assertEqual(data["auditor"], "grok-4.7")
        self.assertEqual(data["planner"], "gemini-3.8-flash-low")
        self.assertEqual(data["scorer"], "gemini-3.8-flash-low")

        # Reset back to template defaults
        subprocess.run([SETUP_SCRIPT, "--defaults"], check=True)


if __name__ == "__main__":
    unittest.main()
