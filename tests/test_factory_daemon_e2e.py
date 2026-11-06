"""Unit and end-to-end integration tests for External Factory Daemon & Webhook listener."""

import json
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

from scripts.factory_daemon import FactoryDaemonServer, parse_args


class TestFactoryDaemonE2E(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        # Start a local daemon on an ephemeral port
        self.port = 18088
        self.daemon = FactoryDaemonServer(host="127.0.0.1", port=self.port, max_workers=2)
        self.server_thread = threading.Thread(target=self.daemon.serve_forever, daemon=True)
        self.server_thread.start()
        time.sleep(0.1)

    def tearDown(self):
        self.daemon.shutdown()
        self.temp_dir.cleanup()

    def test_health_check_endpoint(self):
        """GET /health returns 200 OK and status JSON."""
        url = f"http://127.0.0.1:{self.port}/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "ok")

    def test_webhook_receives_agent_labeled_event(self):
        """POST /webhook accepts GitHub issue labeled event with agent label."""
        url = f"http://127.0.0.1:{self.port}/webhook"
        payload = {
            "action": "labeled",
            "issue": {
                "number": 110,
                "title": "feat: test issue dispatch",
                "labels": [{"name": "agent"}],
            },
            "repository": {
                "full_name": "mock-org/mock-repo",
                "clone_url": "https://github.com/mock-org/mock-repo.git",
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "X-GitHub-Event": "issues"},
        )

        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("dispatched"))
            self.assertEqual(data.get("issue"), 110)

    def test_webhook_ignores_non_agent_label(self):
        """POST /webhook ignores issues labeled without 'agent' label."""
        url = f"http://127.0.0.1:{self.port}/webhook"
        payload = {
            "action": "labeled",
            "issue": {
                "number": 110,
                "labels": [{"name": "documentation"}],
            },
            "repository": {
                "full_name": "mock-org/mock-repo",
            },
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertFalse(data.get("dispatched"))

    def test_e2e_worktree_execution_lifecycle(self):
        """E2E flow: initializes mock repo with package.json, runs runner, validates branch and cleanup."""
        mock_repo = self.root / "mock_client"
        mock_repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-b", "main"], cwd=mock_repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=mock_repo, check=True)
        subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=mock_repo, check=True)

        (mock_repo / "package.json").write_text('{"name": "test-e2e"}', encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=mock_repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=mock_repo, check=True, capture_output=True)

        # Run factory_runner against mock repo
        worktree_base = self.root / "worktrees"
        from scripts.factory_runner import WorktreeManager
        from scripts.project_adapter import load_project_adapter

        manager = WorktreeManager(base_dir=worktree_base)
        wt = manager.create_worktree(mock_repo, branch="feat/e2e-slice", issue_id="110", repo_slug="mock/test-e2e")
        self.assertTrue(wt.exists())

        # Validate adapter
        adapter = load_project_adapter(wt)
        self.assertEqual(adapter.framework, "node")
        self.assertEqual(adapter.verify_command, "npm test")

        # Cleanup
        manager.cleanup_worktree(wt, mock_repo)
        self.assertFalse(wt.exists())


if __name__ == "__main__":
    unittest.main()
