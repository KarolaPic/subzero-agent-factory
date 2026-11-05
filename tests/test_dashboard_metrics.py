"""Unit tests for DashboardMetrics calculation engine and run log parsing."""

import json
import subprocess
import unittest
from pathlib import Path


class TestDashboardMetrics(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).parent.parent
        self.metrics_js_path = self.repo_root / "docs" / "metrics.js"
        self.assertTrue(self.metrics_js_path.exists(), "docs/metrics.js must exist")

    def _eval_js(self, js_code: str):
        """Executes a JavaScript snippet requiring docs/metrics.js and returns parsed JSON."""
        full_code = f"""
        const path = require('path');
        const metrics = require('{self.metrics_js_path.resolve()}');
        const result = (() => {{
            {js_code}
        }})();
        console.log(JSON.stringify(result));
        """
        proc = subprocess.run(
            ["node", "-e", full_code],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(proc.stdout.strip())

    def test_empty_or_whitespace_log(self):
        result = self._eval_js("""
            const raw = '';
            const records = metrics.parseRunLog(raw);
            const m = metrics.computeMetrics(records);
            return { records, m };
        """)
        self.assertEqual(result["records"], [])
        self.assertEqual(result["m"]["totalRuns"], 0)
        self.assertEqual(result["m"]["prsOpened"], 0)
        self.assertEqual(result["m"]["prsMerged"], 0)
        self.assertEqual(result["m"]["avgKickoffToPrSeconds"], 0)
        self.assertEqual(result["m"]["avgPrToReviewSeconds"], 0)
        self.assertEqual(result["m"]["avgReviewToMergeSeconds"], 0)
        self.assertEqual(result["m"]["totalInterventions"], 0)
        self.assertEqual(result["m"]["interventionsPerPr"], 0)

    def test_corrupt_lines_skipped_gracefully(self):
        result = self._eval_js("""
            const raw = 'not-json\\n{"issue": 1, "pr": 10, "result": "merged"}\\n{bad-json';
            const records = metrics.parseRunLog(raw);
            return records;
        """)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["issue"], 1)

    def test_intervention_count_parsing(self):
        result = self._eval_js("""
            return {
                boolFalse: metrics.getInterventionCount(false),
                boolTrue: metrics.getInterventionCount(true),
                objZero: metrics.getInterventionCount({ occurred: false, count: 0 }),
                objMultiple: metrics.getInterventionCount({ occurred: true, count: 3 }),
                objMissingCount: metrics.getInterventionCount({ occurred: true }),
                nullVal: metrics.getInterventionCount(null)
            };
        """)
        self.assertEqual(result["boolFalse"], 0)
        self.assertEqual(result["boolTrue"], 1)
        self.assertEqual(result["objZero"], 0)
        self.assertEqual(result["objMultiple"], 3)
        self.assertEqual(result["objMissingCount"], 1)
        self.assertEqual(result["nullVal"], 0)

    def test_full_metric_computation(self):
        result = self._eval_js("""
            const records = [
                {
                    issue: 101,
                    pr: 10,
                    kickoff_at: "2026-11-05T10:00:00Z",
                    pr_opened_at: "2026-11-05T10:02:00Z", // 120s
                    first_review_at: "2026-11-05T10:03:00Z", // 60s
                    merged_at: "2026-11-05T10:05:00Z", // 120s
                    human_intervened: false,
                    result: "merged",
                    builder: "gemini-3.8-flash-high",
                    auditor: "grok-4.7",
                    pr_score: 9.5
                },
                {
                    issue: 102,
                    pr: 11,
                    kickoff_at: "2026-11-05T11:00:00Z",
                    pr_opened_at: "2026-11-05T11:04:00Z", // 240s
                    first_review_at: "2026-11-05T11:06:00Z", // 120s
                    merged_at: "2026-11-05T11:08:00Z", // 120s
                    human_intervened: { occurred: true, count: 2 },
                    result: "merged",
                    builder: "gemini-3.8-flash-high",
                    auditor: "grok-4.7",
                    pr_score: 8.0
                },
                {
                    issue: 103,
                    pr: null,
                    kickoff_at: "2026-11-05T12:00:00Z",
                    pr_opened_at: null,
                    first_review_at: null,
                    merged_at: null,
                    human_intervened: true,
                    result: "blocked",
                    builder: "gemini-3.8-flash-high",
                    auditor: "grok-4.7",
                    pr_score: null
                }
            ];
            return metrics.computeMetrics(records);
        """)

        # Total runs: 3
        self.assertEqual(result["totalRuns"], 3)
        # PRs opened: 2 (runs 1 and 2)
        self.assertEqual(result["prsOpened"], 2)
        # PRs merged: 2
        self.assertEqual(result["prsMerged"], 2)

        # Kickoff to PR: (120s + 240s) / 2 = 180s
        self.assertEqual(result["avgKickoffToPrSeconds"], 180)
        # PR to first review: (60s + 120s) / 2 = 90s
        self.assertEqual(result["avgPrToReviewSeconds"], 90)
        # Review to merge: (120s + 120s) / 2 = 120s
        self.assertEqual(result["avgReviewToMergeSeconds"], 120)

        # Human interventions: run 1 (0) + run 2 (2) + run 3 (1) = 3 total
        self.assertEqual(result["totalInterventions"], 3)
        # Interventions per PR: 3 / 2 opened PRs = 1.5
        self.assertEqual(result["interventionsPerPr"], 1.5)

    def test_format_duration(self):
        result = self._eval_js("""
            return {
                d0: metrics.formatDuration(0),
                d45: metrics.formatDuration(45),
                d90: metrics.formatDuration(90),
                d3600: metrics.formatDuration(3600)
            };
        """)
        self.assertEqual(result["d0"], "0s")
        self.assertEqual(result["d45"], "45s")
        self.assertEqual(result["d90"], "1m 30s")
        self.assertEqual(result["d3600"], "60m 0s")


if __name__ == "__main__":
    unittest.main()
