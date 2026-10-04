"""Regression tests for SELECT rewards, without the optional AgentRL runtime."""

import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


PROCESSOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "server" / "tasks" / "dbbench" / "result_processor.py"
)
spec = importlib.util.spec_from_file_location("dbbench_result_processor", PROCESSOR_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DBResultProcessor = module.DBResultProcessor


class DBBenchSelectResultTest(unittest.TestCase):
    def compare(self, answer, gold):
        return DBResultProcessor.compare_results(answer, gold, "SELECT")

    def test_multi_column_gold_does_not_reward_empty_answer(self):
        gold = "[('Taiwan', 1), ('United States', 13), ('Canada', 1)]"
        self.assertFalse(self.compare([], gold))
        self.assertTrue(self.compare(
            ["('Canada', 1)", "('Taiwan', 1)", "('United States', 13)"], gold
        ))
        self.assertTrue(self.compare([gold], gold))
        self.assertFalse(self.compare(["Taiwan", "1"], gold))

    def test_decimal_and_null_in_rows(self):
        gold = "[('2003–2006', 4, Decimal('0.0000')), (0, None)]"
        self.assertFalse(self.compare([], gold))
        self.assertTrue(self.compare(
            ["(0, None)", "('2003–2006', 4, Decimal('0.0000'))"], gold
        ))

    def test_single_column_and_empty_result_controls(self):
        self.assertTrue(self.compare(["Canada", "Taiwan"], "[('Taiwan',), ('Canada',)]"))
        self.assertFalse(self.compare([], "[('Taiwan',), ('Canada',)]"))
        self.assertTrue(self.compare([], "[]"))

    def test_missing_and_non_finite_answers_do_not_match_zero(self):
        for answer in (None, ["None"], ["null"], ["undefined"], ["nan"],
                       ["inf"], ["-infinity"], [""]):
            with self.subTest(answer=answer):
                self.assertFalse(self.compare(answer, "[(0,)]"))
        self.assertTrue(self.compare(["0"], "[(0,)]"))

    def test_unparseable_or_truncated_gold_fails_closed(self):
        self.assertFalse(self.compare([], "[('A', 1), ('B'[TRUNCATED]"))
        self.assertFalse(self.compare([], "[Decimal('not a number')]"))

    def test_agent_literal_never_executes_code(self):
        attack = "[(__import__('os').system('echo never'),)]"
        with patch("os.system") as system:
            self.assertFalse(self.compare([attack], "[(0,)]"))
            self.assertFalse(self.compare([], attack))
            system.assert_not_called()

    def test_shipped_training_select_labels(self):
        data_file = Path(__file__).resolve().parents[1] / "data" / "dbbench" / "db_out_new.jsonl"
        select_count = 0
        parsed_rows = 0
        with patch("builtins.print"):
            with data_file.open(encoding="utf-8") as stream:
                for line in stream:
                    entry = json.loads(line)
                    if entry["type"][0] != "SELECT":
                        continue
                    select_count += 1
                    gold = entry["label"]
                    self.assertEqual(self.compare([], gold), gold == "[]", select_count)
                    cleaned = DBResultProcessor._clean_mysql_result(gold)
                    if cleaned is not None:
                        parsed_rows += 1
                        self.assertTrue(self.compare(cleaned, gold), select_count)
        self.assertGreater(select_count, 1000)
        self.assertGreater(parsed_rows, 900)

    def test_quoted_list_items_keep_previous_matching_behavior(self):
        data_dir = Path(__file__).resolve().parents[1] / "data" / "dbbench"
        checked = 0
        with patch("builtins.print"):
            for name in ("standard.jsonl", "dev.jsonl"):
                with (data_dir / name).open(encoding="utf-8") as stream:
                    for line_number, line in enumerate(stream, 1):
                        entry = json.loads(line)
                        if entry["type"][0] in ("INSERT", "DELETE", "UPDATE"):
                            continue
                        gold = entry["label"]
                        quoted_answer = [f"'{item}'" for item in gold]
                        self.assertTrue(
                            self.compare(quoted_answer, gold),
                            f"{name}:{line_number}",
                        )
                        checked += 1
        self.assertEqual(checked, 120)


if __name__ == "__main__":
    unittest.main()
