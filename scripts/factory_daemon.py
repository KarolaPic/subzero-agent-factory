#!/usr/bin/env python3
"""External Core Factory Webhook Listener Daemon.

Listens for GitHub issue webhook events (specifically 'labeled' with 'agent'),
and asynchronously dispatches factory_runner.py with thread pool concurrency control.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("factory_daemon")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class WebhookHandler(BaseHTTPRequestHandler):
    server: FactoryDaemonServer  # Type hint for IDE/mypy

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {"status": "ok", "concurrency": self.server.max_workers}
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            payload = json.loads(post_data.decode("utf-8"))
        except Exception as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Invalid JSON: {e}"}).encode("utf-8"))
            return

        action = payload.get("action", "")
        issue = payload.get("issue", {})
        repo = payload.get("repository", {})

        # Check for 'agent' label
        labels = [lbl.get("name", "") for lbl in issue.get("labels", [])]
        has_agent_label = "agent" in labels

        if has_agent_label and action in ("labeled", "opened", "reopened", "synchronize", ""):
            issue_num = issue.get("number")
            repo_slug = repo.get("full_name") or repo.get("name")
            clone_url = repo.get("clone_url") or repo_slug

            # Dispatch in worker thread pool
            self.server.dispatch_job(repo_slug or "unknown", issue_num, clone_url)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "dispatched": True,
                "issue": issue_num,
                "repository": repo_slug,
                "message": f"Dispatched issue #{issue_num} to runner pool",
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "dispatched": False,
                "reason": "Event ignored (no 'agent' label or unhandled action)",
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))

    def log_message(self, format, *args):
        # Override to suppress noisy default access logs in tests
        pass


class FactoryDaemonServer(HTTPServer):
    """HTTP Server listening for GitHub issue webhooks with thread pool dispatch."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8088, max_workers: int = 2):
        super().__init__((host, port), WebhookHandler)
        self.max_workers = max_workers
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.active_jobs = []

    def dispatch_job(self, repo_slug: str, issue_num: int, clone_url: str) -> None:
        logger.info("Queuing job for %s #%s in runner thread pool...", repo_slug, issue_num)
        self.executor.submit(self._run_job, repo_slug, issue_num, clone_url)

    def _run_job(self, repo_slug: str, issue_num: int, clone_url: str) -> None:
        logger.info("Starting execution for %s #%s", repo_slug, issue_num)
        # Placeholder or direct dispatch to factory_runner.py
        branch = f"feat/{issue_num}-agent"
        cmd = [
            sys.executable,
            str(Path(__file__).parent / "factory_runner.py"),
            "--repo", clone_url,
            "--issue", str(issue_num),
            "--branch", branch,
            "--dry-run",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            logger.info("Runner result for %s #%s (exit %d): %s", repo_slug, issue_num, res.returncode, res.stdout.strip())
        except Exception as e:
            logger.error("Runner execution failed for %s #%s: %s", repo_slug, issue_num, e)

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False)
        super().shutdown()
        self.server_close()


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="External Core Factory Webhook Listener Daemon")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8088, help="Port to listen on (default: 8088)")
    parser.add_argument("--concurrency", type=int, default=2, help="Maximum concurrent worker jobs (default: 2)")
    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> int:
    parsed = parse_args(args)
    logger.info("Starting Factory Webhook Daemon on %s:%d (concurrency=%d)...", parsed.host, parsed.port, parsed.concurrency)
    server = FactoryDaemonServer(host=parsed.host, port=parsed.port, max_workers=parsed.concurrency)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down daemon...")
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
