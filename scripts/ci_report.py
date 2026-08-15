#!/usr/bin/env python3
"""Report aggregate pass rates with 95% Wilson CIs and paired McNemar.

Accepts a per-instance results JSON in one of two shapes:

* a mapping ``{task_id: true/false}``
* a list of records ``[{"id": ..., "success": true/false}, ...]``

and prints the aggregate pass rate with a 95% Wilson score interval. With
``--compare``, runs an exact paired McNemar test between two agents over
their shared task set.

The input file is a convenience interface: it must be derived from
AgentBench run outputs. This script does not parse native artifacts such
as ``overall.json`` (task-level aggregate metrics, format varies per task)
or the raw ``db_out_new.jsonl``/``dev.jsonl`` trajectory logs.

Example::

    python scripts/ci_report.py --results agent_a.json
    python scripts/ci_report.py --results agent_a.json --compare agent_b.json
"""

import argparse
import json
import math
from collections import OrderedDict


def wilson_ci(successes: int, n: int, z: float = 1.96):
    """(lower, upper) Wilson score interval for a proportion."""
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def paired_mcnemar(a_only: int, b_only: int, two_sided: bool = True) -> float:
    """Exact binomial p-value for the paired McNemar test."""
    n = a_only + b_only
    if n == 0:
        return 1.0
    k = min(a_only, b_only)
    tail = 0.0
    for i in range(k + 1):
        tail += math.comb(n, i) / (2 ** n)
    return min(1.0, 2 * tail) if two_sided else tail


def load_instances(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return OrderedDict((str(k), bool(v)) for k, v in data.items())
    return OrderedDict((str(r.get("id", i)), bool(r["success"])) for i, r in enumerate(data))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, help="per-instance results JSON")
    parser.add_argument("--compare", help="second results JSON for McNemar")
    args = parser.parse_args()

    per_task = load_instances(args.results)
    n = len(per_task)
    if n == 0:
        raise SystemExit("no instances found")
    successes = sum(per_task.values())
    lo, hi = wilson_ci(successes, n)
    print(f"tasks: {n}")
    print(f"pass rate: {successes / n:.4f}  95% CI [{lo:.4f}, {hi:.4f}]")

    if args.compare:
        other = load_instances(args.compare)
        shared = [t for t in per_task if t in other]
        if not shared:
            raise SystemExit("no shared tasks between the two result files")
        a_only = sum(1 for t in shared if per_task[t] and not other[t])
        b_only = sum(1 for t in shared if other[t] and not per_task[t])
        both = sum(1 for t in shared if per_task[t] and other[t])
        p = paired_mcnemar(a_only, b_only)
        print(f"paired comparison on {len(shared)} shared tasks")
        print(f"both: {both}  | A-only: {a_only}  | B-only: {b_only}")
        print(f"McNemar two-sided p: {p:.4f}")


if __name__ == "__main__":
    main()
