"""Opt-in live MySQL SELECT checks, without the optional AgentRL allocator.

DBBENCH_MYSQL_PORT=33060 python -m unittest discover -s tests -p test_dbbench_mysql.py -v
Requires mysql-connector-python with its aio API and a disposable localhost server.
The actual Database/MySQLDatabase class bodies are loaded from interaction.py;
only construction/connection allocation is bypassed. This is not an AgentRL test.
"""

import ast
import asyncio
import importlib.util
import logging
import os
import unittest
from pathlib import Path

DB_DIRECTORY = Path(__file__).resolve().parents[1] / "src/server/tasks/dbbench"
spec = importlib.util.spec_from_file_location(
    "mysql_grading_processor", DB_DIRECTORY / "result_processor.py"
)
processor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(processor)


@unittest.skipUnless(
    os.environ.get("DBBENCH_MYSQL_PORT"),
    "set DBBENCH_MYSQL_PORT for live localhost checks",
)
class LiveMySQLSelectTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import mysql.connector.aio as connector

        tree = ast.parse((DB_DIRECTORY / "interaction.py").read_text(encoding="utf-8"))
        classes = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name in {"Database", "MySQLDatabase"}
        ]
        module = ast.parse("from __future__ import annotations\n")
        module.body.extend(classes)
        namespace = {
            "asyncio": asyncio,
            "logging": logging,
            "mysql_connector": connector,
        }
        # Execute only repository class definitions, never SQL results or agent text.
        exec(compile(module, str(DB_DIRECTORY / "interaction.py"), "exec"), namespace)  # noqa: S102
        database_class = namespace["MySQLDatabase"]
        self.database = object.__new__(database_class)
        self.database.logger = logging.getLogger("live_dbbench_mysql")
        self.database._conn = await connector.connect(
            host="127.0.0.1",
            port=int(os.environ["DBBENCH_MYSQL_PORT"]),
            user="root",
            password=os.environ.get("DBBENCH_MYSQL_PASSWORD", ""),
            connection_timeout=10,
        )
        self.database.database = None

    async def asyncTearDown(self):
        await self.database._conn.close()

    async def test_multi_column_decimal_null_actual_driver_output(self):
        gold = await self.database.execute(
            "SELECT 'A' AS name, CAST(1.25 AS DECIMAL(10,2)) AS amount, NULL AS optional "
            "UNION ALL SELECT 'B', CAST(0 AS DECIMAL(10,2)), NULL"
        )
        self.assertIn("Decimal('1.25')", gold)
        self.assertIn("None", gold)
        self.assertTrue(
            processor.DBResultProcessor.compare_results(
                ["('B', Decimal('0.00'), None)", "('A', Decimal('1.25'), None)"],
                gold,
                "SELECT",
            )
        )
        self.assertFalse(
            processor.DBResultProcessor.compare_results([], gold, "SELECT")
        )

    async def test_genuine_empty_query_result(self):
        gold = await self.database.execute("SELECT 0 WHERE FALSE")
        self.assertEqual(gold, "[]")
        self.assertTrue(processor.DBResultProcessor.compare_results([], gold, "SELECT"))
        self.assertFalse(
            processor.DBResultProcessor.compare_results(["0"], gold, "SELECT")
        )

    async def test_zero_is_not_missing_or_invalid_answer(self):
        gold = await self.database.execute("SELECT 0")
        self.assertEqual(gold, "[(0,)]")
        self.assertTrue(
            processor.DBResultProcessor.compare_results(["0"], gold, "SELECT")
        )
        for answer in (None, [], ["None"], ["nan"], ["not a result"]):
            with self.subTest(answer=answer):
                self.assertFalse(
                    processor.DBResultProcessor.compare_results(answer, gold, "SELECT")
                )

    async def test_single_column_and_quote_compatibility(self):
        gold = await self.database.execute("SELECT 'Canada' UNION ALL SELECT 'Taiwan'")
        self.assertTrue(
            processor.DBResultProcessor.compare_results(
                ["'Taiwan'", "'Canada'"], gold, "SELECT"
            )
        )
        self.assertFalse(
            processor.DBResultProcessor.compare_results([], gold, "SELECT")
        )


if __name__ == "__main__":
    unittest.main()
