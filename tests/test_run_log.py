import json
import multiprocessing
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.run_log import (
    RunLogError,
    read_runs,
    record_run,
    resolve_runs_dir,
    validate_run_record,
)


def _worker_append(args):
    runs_dir, worker_id, iterations = args
    for i in range(iterations):
        record_run(
            issue=100 + worker_id,
            pr=200 + i,
            result="merged",
            builder="gemini-3.8-flash-high",
            auditor="grok-4.7",
            human_intervened={"occurred": False, "count": 0},
            pr_score=9.5,
            review_result="approved",
            review_rounds=1,
            reviewer_model="grok-4.7",
            runs_dir=Path(runs_dir),
        )


class TestRunLog(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_run_log_")
        self.runs_dir = Path(self.test_dir) / ".factory" / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_schema_file_exists_and_is_valid_json(self):
        schema_path = Path(".factory/schemas/run.schema.json")
        self.assertTrue(schema_path.exists())
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        self.assertEqual(schema.get("type"), "object")
        self.assertFalse(schema.get("additionalProperties"))
        required = set(schema.get("required", []))
        expected_fields = {
            "issue",
            "pr",
            "kickoff_at",
            "pr_opened_at",
            "first_review_at",
            "merged_at",
            "human_intervened",
            "result",
            "builder",
            "auditor",
            "pr_score",
            "review_result",
            "review_rounds",
            "reviewer_model",
        }
        self.assertEqual(required, expected_fields)

    def test_record_run_basic(self):
        record = record_run(
            issue=38,
            pr=45,
            result="merged",
            builder="gemini-3.8-flash-high",
            auditor="grok-4.7",
            human_intervened={"occurred": True, "count": 1},
            pr_score=9.8,
            runs_dir=self.runs_dir,
        )

        self.assertEqual(record["issue"], 38)
        self.assertEqual(record["pr"], 45)
        self.assertEqual(record["result"], "merged")
        self.assertEqual(record["builder"], "gemini-3.8-flash-high")
        self.assertEqual(record["auditor"], "grok-4.7")
        self.assertEqual(record["pr_score"], 9.8)
        self.assertEqual(record["human_intervened"], {"occurred": True, "count": 1})
        self.assertIsNone(record["review_result"])
        self.assertIsNone(record["review_rounds"])
        self.assertIsNone(record["reviewer_model"])
        self.assertIsNotNone(record["kickoff_at"])

        # Verify file content on disk
        runs_file = self.runs_dir / "runs.jsonl"
        self.assertTrue(runs_file.exists())
        lines = read_runs(self.runs_dir)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["issue"], 38)

    def test_record_run_with_review_metrics(self):
        record = record_run(
            issue=70,
            pr=78,
            result="merged",
            builder="gemini-3.8-flash-high",
            auditor="grok-4.7",
            human_intervened=False,
            pr_score=9.9,
            review_result="approved",
            review_rounds=2,
            reviewer_model="grok-4.7",
            runs_dir=self.runs_dir,
        )

        self.assertEqual(record["review_result"], "approved")
        self.assertEqual(record["review_rounds"], 2)
        self.assertEqual(record["reviewer_model"], "grok-4.7")

        lines = read_runs(self.runs_dir)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["review_result"], "approved")
        self.assertEqual(lines[0]["review_rounds"], 2)
        self.assertEqual(lines[0]["reviewer_model"], "grok-4.7")

    def test_review_validation_rules(self):
        # 1. Invalid review_result enum
        with self.assertRaises(RunLogError) as ctx:
            record_run(
                issue=70,
                result="merged",
                builder="gemini-3.8-flash-high",
                auditor="grok-4.7",
                review_result="rejected",
                runs_dir=self.runs_dir,
            )
        self.assertIn("Field 'review_result'", str(ctx.exception))

        # 2. Invalid review_rounds (exceeding max 3)
        with self.assertRaises(RunLogError) as ctx:
            record_run(
                issue=70,
                result="merged",
                builder="gemini-3.8-flash-high",
                auditor="grok-4.7",
                review_result="changes_requested",
                review_rounds=4,
                reviewer_model="grok-4.7",
                runs_dir=self.runs_dir,
            )
        self.assertIn("Field 'review_rounds'", str(ctx.exception))

        # 3. Invalid review_rounds (< 1 when review was performed)
        with self.assertRaises(RunLogError) as ctx:
            record_run(
                issue=70,
                result="merged",
                builder="gemini-3.8-flash-high",
                auditor="grok-4.7",
                review_result="approved",
                review_rounds=0,
                reviewer_model="grok-4.7",
                runs_dir=self.runs_dir,
            )
        self.assertIn("Field 'review_rounds'", str(ctx.exception))

        # 4. Valid skipped review
        rec_skipped = record_run(
            issue=70,
            result="merged",
            builder="gemini-3.8-flash-high",
            auditor="grok-4.7",
            review_result="skipped",
            review_rounds=0,
            reviewer_model=None,
            runs_dir=self.runs_dir,
        )
        self.assertEqual(rec_skipped["review_result"], "skipped")
        self.assertEqual(rec_skipped["review_rounds"], 0)

        # 5. Invalid reviewer_model (empty string)
        with self.assertRaises(RunLogError) as ctx:
            record_run(
                issue=70,
                result="merged",
                builder="gemini-3.8-flash-high",
                auditor="grok-4.7",
                review_result="approved",
                review_rounds=1,
                reviewer_model="",
                runs_dir=self.runs_dir,
            )
        self.assertIn("Field 'reviewer_model'", str(ctx.exception))

    def test_validation_errors(self):
        # 1. Missing required field
        invalid_rec = {
            "issue": 1,
            "pr": None,
            "kickoff_at": "2026-11-05T12:00:00Z",
        }
        with self.assertRaises(RunLogError):
            validate_run_record(invalid_rec)

        # 2. Unexpected extra field (token or secret leakage protection)
        with self.assertRaises(RunLogError):
            record_run(
                issue=1,
                result="merged",
                builder="gemini-3.8-flash-high",
                auditor="grok-4.7",
                runs_dir=self.runs_dir,
            )
            bad_rec = read_runs(self.runs_dir)[0]
            bad_rec["secret_token"] = "gho_xxxx"
            validate_run_record(bad_rec)

        # 3. Invalid result enum
        with self.assertRaises(RunLogError):
            record_run(
                issue=1,
                result="unknown_status",
                builder="gemini-3.8-flash-high",
                auditor="grok-4.7",
                runs_dir=self.runs_dir,
            )

        # 4. Invalid timestamp
        with self.assertRaises(RunLogError):
            record_run(
                issue=1,
                kickoff_at="not-a-timestamp",
                result="merged",
                builder="gemini-3.8-flash-high",
                auditor="grok-4.7",
                runs_dir=self.runs_dir,
            )

    def test_multiprocess_concurrency(self):
        num_workers = 4
        iterations = 5
        total_records = num_workers * iterations

        args_list = [(str(self.runs_dir), w, iterations) for w in range(num_workers)]
        with multiprocessing.Pool(processes=num_workers) as pool:
            pool.map(_worker_append, args_list)

        runs_file = self.runs_dir / "runs.jsonl"
        with open(runs_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        self.assertEqual(len(lines), total_records)

        records = [json.loads(line) for line in lines]
        for rec in records:
            validate_run_record(rec)
            self.assertEqual(rec["result"], "merged")
            self.assertEqual(rec["builder"], "gemini-3.8-flash-high")
            self.assertEqual(rec["review_result"], "approved")
            self.assertEqual(rec["review_rounds"], 1)
            self.assertEqual(rec["reviewer_model"], "grok-4.7")

    def test_run_log_cli_record_score_and_validate(self):
        import subprocess
        # 1. Test CLI record with --score
        cmd_rec = [
            "python3",
            "scripts/run_log.py",
            "record",
            "--issue", "60",
            "--pr", "65",
            "--result", "merged",
            "--score", "9.7",
            "--runs-dir", str(self.runs_dir),
        ]
        res = subprocess.run(cmd_rec, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"run_log record failed: {res.stderr}")
        self.assertIn("score: 9.7", res.stdout)

        # 2. Test CLI validate
        cmd_val = [
            "python3",
            "scripts/run_log.py",
            "validate",
            "--runs-dir", str(self.runs_dir),
        ]
        res_val = subprocess.run(cmd_val, capture_output=True, text=True)
        self.assertEqual(res_val.returncode, 0, f"run_log validate failed: {res_val.stderr}")
        self.assertIn("Validated 1 run record(s)", res_val.stdout)

        # 3. Read back and verify pr_score
        runs = read_runs(self.runs_dir)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["issue"], 60)
        self.assertEqual(runs[0]["pr"], 65)
        self.assertEqual(runs[0]["pr_score"], 9.7)


if __name__ == "__main__":
    unittest.main()

