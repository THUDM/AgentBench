import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.run_coverage import (
    MANIFEST,
    analyze_coverage,
    report_task,
    save_sample_manifest,
)


class CoverageTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.task = self.root / "outputs" / "run" / "model" / "dbbench"
        self.task.mkdir(parents=True)

    def log(self, index, status="completed", error=None, result=None):
        record = {
            "index": index,
            "error": error,
            "output": None
            if error
            else {"index": index, "status": status, "result": result},
            "time": {"timestamp": 1},
        }
        with (self.task / ("error.jsonl" if error else "runs.jsonl")).open(
            "a", encoding="utf-8"
        ) as stream:
            stream.write(json.dumps(record) + "\n")

    def test_partial_ten_samples_visible_without_overall(self):
        save_sample_manifest(self.task, list(range(10)))
        for i in range(8):
            self.log(i)
        for i in (8, 9):
            self.log(i, error="NETWORK_ERROR")
        report = analyze_coverage(self.root / "outputs")["tasks"][0]
        self.assertEqual(report["terminal_count"], 8)
        self.assertEqual(report["coverage_fraction"], 0.8)
        self.assertEqual(report["infrastructure_error_ids"], [8, 9])
        self.assertEqual(report["pending_ids"], [8, 9])
        self.assertFalse(report["is_complete"])
        self.assertEqual(report["score_status"], "missing_overall")

    def test_complete_run_preserves_existing_score_bytes(self):
        save_sample_manifest(self.task, [0, 1])
        self.log(0)
        self.log(1, status="agent invalid action")
        score = b'{"custom": {"accuracy": 0.5}}\n'
        (self.task / "overall.json").write_bytes(score)
        report = report_task(self.task)
        self.assertTrue(report["is_complete"])
        self.assertEqual(report["score_status"], "complete")
        self.assertEqual((self.task / "overall.json").read_bytes(), score)

    def test_retries_then_success_only_one_terminal_sample(self):
        save_sample_manifest(self.task, ["one"])
        self.log("one", error="NETWORK_ERROR")
        self.log("one", error="START_FAILED")
        self.log("one", result=0)
        report = report_task(self.task)
        self.assertEqual(report["terminal_count"], 1)
        self.assertEqual(report["samples"][0]["recorded_attempt_count"], 3)
        self.assertEqual(report["infrastructure_error_ids"], [])
        self.assertTrue(report["is_complete"])

    def test_duplicate_resume_does_not_double_count(self):
        save_sample_manifest(self.task, [0])
        self.log(0, result=0)
        self.log(0, result=0)
        report = report_task(self.task)
        self.assertEqual(report["terminal_count"], 1)
        self.assertEqual(report["duplicate_terminal_ids"], [0])
        self.assertTrue(report["is_complete"])

    def test_conflicting_terminal_records_do_not_choose_best_result(self):
        save_sample_manifest(self.task, [0])
        self.log(0, status="agent invalid action", result=0)
        self.log(0, result=1)
        report = report_task(self.task)
        self.assertEqual(
            report["samples"][0]["terminal_status"], "agent invalid action"
        )
        self.assertEqual(report["conflicting_terminal_ids"], [0])
        self.assertFalse(report["is_complete"])

    def test_malformed_tail_is_reported(self):
        save_sample_manifest(self.task, [0, 1])
        self.log(0)
        with (self.task / "runs.jsonl").open("a") as stream:
            stream.write('{"index":1')
        report = report_task(self.task)
        self.assertEqual(report["terminal_count"], 1)
        self.assertEqual(report["diagnostics"][0]["line"], 2)
        self.assertFalse(report["is_complete"])

    def test_missing_or_invalid_manifest_never_guesses_denominator(self):
        self.log(99)
        for content in (None, '{"schema_version":1,"expected_ids":[true]}', "{}"):
            if content is not None:
                (self.task / MANIFEST).write_text(content)
            report = report_task(self.task)
            self.assertIsNone(report["expected_count"])
            self.assertIsNone(report["coverage_fraction"])
            self.assertIsNone(report["is_complete"])

    def test_integer_and_string_indices_are_distinct(self):
        save_sample_manifest(self.task, [0, "0"])
        self.log(0)
        report = report_task(self.task)
        self.assertEqual(report["pending_ids"], ["0"])
        self.assertEqual(report["coverage_fraction"], 0.5)

    def test_malformed_overall_and_invalid_log_schema_are_diagnosed(self):
        save_sample_manifest(self.task, [0])
        self.log(0)
        (self.task / "overall.json").write_text("[]")
        with (self.task / "runs.jsonl").open("a") as stream:
            stream.write('{"index":false,"output":{"status":"completed"}}\n')
            stream.write('{"index":1,"output":{"status":"completed","result":NaN}}\n')
        report = report_task(self.task)
        self.assertEqual(len(report["diagnostics"]), 3)
        self.assertEqual(report["score_status"], "inconsistent_logs")
        self.assertFalse(report["is_complete"])

    def test_unstarted_manifest_and_empty_plan(self):
        save_sample_manifest(self.task, [0])
        report = report_task(self.task)
        self.assertEqual(report["coverage_fraction"], 0.0)
        self.assertFalse(report["is_complete"])
        empty = self.task.parent / "empty"
        save_sample_manifest(empty, [])
        self.assertTrue(report_task(empty)["is_complete"])
        self.assertIsNone(report_task(empty)["coverage_fraction"])

    def test_running_and_unexpected_results_cannot_complete_plan(self):
        save_sample_manifest(self.task, [0])
        self.log(0, status="running")
        self.log(1)
        report = report_task(self.task)
        self.assertEqual(report["terminal_count"], 0)
        self.assertEqual(report["unexpected_ids"], [1])
        self.assertFalse(report["is_complete"])

    def test_manifest_is_stable_and_changed_resume_rejected(self):
        save_sample_manifest(self.task, [0])
        before = (self.task / MANIFEST).read_bytes()
        save_sample_manifest(self.task, [0])
        self.assertEqual((self.task / MANIFEST).read_bytes(), before)
        with self.assertRaises(ValueError):
            save_sample_manifest(self.task, [1])
        with self.assertRaises(ValueError):
            save_sample_manifest(self.task, [0, 0])
        (self.task / MANIFEST).write_text('{"schema_version":1,"expected_ids":[false]}')
        with self.assertRaises(ValueError):
            save_sample_manifest(self.task, [0])

    def test_public_cli_writes_sidecar_and_protects_sources(self):
        save_sample_manifest(self.task, [0, 1])
        self.log(0)
        target = self.root / "coverage.json"
        command = [
            sys.executable,
            "-m",
            "src.run_coverage",
            "--output",
            str(self.root / "outputs"),
        ]
        result = subprocess.run(
            command + ["--save", str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 of 2 terminal", result.stdout)
        self.assertEqual(json.loads(target.read_text())["tasks"][0]["pending_ids"], [1])
        before = (self.task / "runs.jsonl").read_bytes()
        result = subprocess.run(
            command + ["--save", str(self.task / "runs.jsonl")],
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.task / "runs.jsonl").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
