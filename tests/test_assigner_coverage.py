"""Exercise the real assigner initializer with in-process task/agent clients."""

import importlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from src.run_coverage import MANIFEST, report_task


class AssignerCoverageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.typings import AssignmentConfig, InstanceFactory

        cls.config_class = AssignmentConfig
        cls.factory_class = InstanceFactory
        # Do not import src.client.agents (optional fastchat/model dependencies).
        package = types.ModuleType("src.client")
        package.__path__ = [str(Path(__file__).resolve().parents[1] / "src" / "client")]
        with patch.dict(sys.modules, {"src.client": package}):
            package.TaskClient = importlib.import_module("src.client.task").TaskClient
            package.AgentClient = importlib.import_module(
                "src.client.agent"
            ).AgentClient
            spec = importlib.util.spec_from_file_location(
                "src.assigner_coverage_test",
                Path(__file__).resolve().parents[1] / "src" / "assigner.py",
            )
            cls.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.module)

    def test_actual_indices_are_saved_before_run_and_preserved_on_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "outputs"
            config = self.config_class.parse_obj(
                {
                    "assignments": [{"agent": "model", "task": "dbbench"}],
                    "concurrency": {"agent": {"model": 1}, "task": {"dbbench": 1}},
                    "definition": {
                        "agent": {"model": {"module": "fake.Agent"}},
                        "task": {"dbbench": {"module": "fake.Task"}},
                    },
                    "output": str(output),
                }
            )
            fake_task = types.SimpleNamespace(get_indices=lambda: [2, 5, 8])

            def create(factory):
                return fake_task if factory.module == "fake.Task" else object()

            with patch.object(self.factory_class, "create", create):
                assigner = self.module.Assigner(config)
                directory = output / "model" / "dbbench"
                manifest_before = (directory / MANIFEST).read_bytes()
                self.assertEqual(json.loads(manifest_before)["expected_ids"], [2, 5, 8])
                self.assertEqual(
                    assigner.remaining_tasks["model"]["dbbench"], [2, 5, 8]
                )
                record = {
                    "index": 5,
                    "error": None,
                    "output": {"index": 5, "status": "completed", "result": 0},
                    "time": {},
                }
                (directory / "runs.jsonl").write_text(
                    json.dumps(record) + "\n", encoding="utf-8"
                )
                resumed = self.module.Assigner(config)
                self.assertEqual(resumed.remaining_tasks["model"]["dbbench"], [2, 8])
                self.assertEqual((directory / MANIFEST).read_bytes(), manifest_before)
                self.assertEqual(report_task(directory)["terminal_count"], 1)
                fake_task.get_indices = lambda: [2, 5, 8, 9]
                with self.assertRaisesRegex(ValueError, "Task indices changed"):
                    self.module.Assigner(config)
                self.assertEqual((directory / MANIFEST).read_bytes(), manifest_before)


if __name__ == "__main__":
    unittest.main()
