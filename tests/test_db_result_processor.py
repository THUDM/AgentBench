"""Regression tests for DBBench answer parsing.

The DBBench result processor is imported in isolation because its normal task
module also imports the optional database worker stack.  These tests exercise
the parser without installing or starting MySQL, Docker, or AgentRL.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "server" / "tasks" / "dbbench" / "result_processor.py"


def load_processor():
    package = types.ModuleType("agentbench_dbbench")
    package.__path__ = [str(MODULE_PATH.parent)]
    interaction = types.ModuleType("agentbench_dbbench.interaction")

    class Database:
        pass

    interaction.Database = Database
    sys.modules[package.__name__] = package
    sys.modules[interaction.__name__] = interaction

    spec = importlib.util.spec_from_file_location(
        "agentbench_dbbench.result_processor", MODULE_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.DBResultProcessor


DBResultProcessor = load_processor()


class DBResultProcessorTests(unittest.TestCase):
    def test_mysql_tuple_result_is_parsed(self):
        self.assertEqual(
            DBResultProcessor._clean_mysql_result("[(293.0,), ('ok',)]"),
            ["293.0", "ok"],
        )

    def test_list_result_is_parsed(self):
        self.assertEqual(
            DBResultProcessor._clean_answer("[1, 'two', (3,)]"),
            ["1", "two", "3"],
        )

    def test_model_controlled_text_is_never_executed(self):
        sentinel = "AGENTBENCH_LITERAL_EVAL_SENTINEL"
        os.environ.pop(sentinel, None)
        payload = "[(__import__('os').environ.__setitem__('" + sentinel + "', '1'),)]"

        DBResultProcessor._clean_mysql_result(payload)
        DBResultProcessor._clean_answer(payload)

        self.assertNotIn(sentinel, os.environ)


if __name__ == "__main__":
    unittest.main()
