import os
import subprocess
import unittest
import yaml

WORKFLOW_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".github", "workflows", "notify-grok.yml")
)


def get_on_section(data):
    return data.get("on") if "on" in data else data.get(True, {})


def simulate_event(workflow_types, job_if_expr, action, label_name, issue_labels):
    # Simulates GitHub Actions intake logic
    if action not in workflow_types:
        return False
    # Evaluate if condition
    if job_if_expr == "github.event.label.name == 'agent'":
        return action == "labeled" and label_name == "agent"
    elif "(github.event.action == 'opened' && contains(github.event.issue.labels.*.name, 'agent'))" in job_if_expr:
        cond_opened = action == "opened" and "agent" in issue_labels
        cond_labeled = action == "labeled" and label_name == "agent"
        return cond_opened or cond_labeled
    return False


class TestNotifyGrok(unittest.TestCase):
    def test_workflow_structure(self):
        self.assertTrue(os.path.exists(WORKFLOW_PATH), f"Workflow file not found at {WORKFLOW_PATH}")
        with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # 1. Trigger must only be 'labeled' (NOT 'opened' to avoid duplicate burst)
        on_section = get_on_section(data)
        issues_config = on_section.get("issues", {})
        types = issues_config.get("types", [])
        self.assertEqual(types, ["labeled"], f"Expected types to be exactly ['labeled'], got {types}")

        # 2. Job 'if' condition must strictly check github.event.label.name == 'agent'
        job = data.get("jobs", {}).get("notify-grok", {})
        job_if = job.get("if", "").strip()
        self.assertEqual(
            job_if,
            "github.event.label.name == 'agent'",
            f"Expected job if to be \"github.event.label.name == 'agent'\", got \"{job_if}\"",
        )

        # 3. Concurrency group per issue with cancel-in-progress: false
        concurrency = job.get("concurrency", {})
        self.assertIn(
            "github.event.issue.number",
            str(concurrency.get("group", "")),
            "Concurrency group must include issue number",
        )
        self.assertFalse(concurrency.get("cancel-in-progress"), "cancel-in-progress must be false")

        # 4. Flaky gh run list dedup step must be removed
        steps = job.get("steps", [])
        step_names = [s.get("name", "") for s in steps]
        self.assertNotIn(
            "Deduplicate initial creation burst",
            step_names,
            "Flaky deduplicate step must be removed",
        )

        # 5. Checkout step must exist to read models.yml
        checkout_step = next((s for s in steps if "Checkout repository" in s.get("name", "")), None)
        self.assertIsNotNone(checkout_step, "Checkout repository step must exist")

        # 6. Send step must build stable idempotency_key repo#issue and pass models
        send_step = next((s for s in steps if "Send issue event to Grok Bot webhook" in s.get("name", "")), None)
        self.assertIsNotNone(send_step, "Send step must exist")
        run_script = send_step.get("run", "")
        self.assertIn(
            'IDEMPOTENCY_KEY="${{ github.repository }}#${{ github.event.issue.number }}"',
            run_script,
            "Must define IDEMPOTENCY_KEY",
        )
        self.assertIn("idempotency_key", run_script, "Must pass idempotency_key to jq")
        self.assertIn("delivery_id", run_script, "Must keep delivery_id in jq")
        self.assertIn("labels", run_script, "Must keep labels in jq")
        self.assertIn("models", run_script, "Must pass models to jq")
        self.assertIn("models.yml", run_script, "Must read models.yml")
        self.assertIn("validate_models.py", run_script, "Must validate models.yml before dispatching webhook")

    def test_simulation_reproduction(self):
        with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        on_section = get_on_section(data)
        workflow_types = on_section.get("issues", {}).get("types", [])
        job_if_expr = data.get("jobs", {}).get("notify-grok", {}).get("if", "").strip()

        # Case: Issue opened with ['bug', 'agent']
        events = [
            {"action": "opened", "label_name": None, "issue_labels": ["bug", "agent"]},
            {"action": "labeled", "label_name": "bug", "issue_labels": ["bug", "agent"]},
            {"action": "labeled", "label_name": "agent", "issue_labels": ["bug", "agent"]},
        ]
        dispatches = [
            e
            for e in events
            if simulate_event(workflow_types, job_if_expr, e["action"], e["label_name"], e["issue_labels"])
        ]

        # In the bug state, dispatches == 2 (opened + labeled agent).
        # In the fixed state, dispatches == 1 (only labeled agent).
        self.assertEqual(
            len(dispatches),
            1,
            f"Expected exactly 1 dispatch on issue creation with 'agent', but got {len(dispatches)}: {dispatches}",
        )

    def test_jq_payload_transformation(self):
        sample_event = '{"issue":{"number":42,"labels":[{"name":"bug"},{"name":"agent"}]}}'
        idempotency_key = "cesarchavezcal/subzero-agent-factory#42"
        delivery_id = "42-12345-1"
        run_id = "12345"
        models_json = '{"builder":"gemini-3.8-flash-high","auditor":"grok-4.7","planner":"gemini-3.8-flash-high","epic_planner":"gemini-3.8-flash-high","subagents":"gemini-3.8-flash-high"}'
        cmd = [
            "jq",
            "--arg", "idempotency_key", idempotency_key,
            "--arg", "delivery_id", delivery_id,
            "--arg", "run_id", run_id,
            "--argjson", "models", models_json,
            '.idempotency_key = $idempotency_key | .delivery_id = $delivery_id | .run_id = $run_id | .labels = [(.issue.labels // [])[].name] | .models = $models',
        ]
        res = subprocess.run(cmd, input=sample_event, text=True, capture_output=True, check=True)
        import json
        out = json.loads(res.stdout)
        self.assertEqual(out["idempotency_key"], idempotency_key)
        self.assertEqual(out["delivery_id"], delivery_id)
        self.assertEqual(out["run_id"], run_id)
        self.assertEqual(out["labels"], ["bug", "agent"])
        self.assertEqual(out["models"]["builder"], "gemini-3.8-flash-high")
        self.assertEqual(out["models"]["auditor"], "grok-4.7")


if __name__ == "__main__":
    unittest.main()
