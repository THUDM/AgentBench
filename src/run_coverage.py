"""Report legacy assigner log coverage without calculating benchmark scores."""

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

# SampleStatus values serialized by the legacy TaskClient.
TERMINAL_STATUSES = {
    "completed",
    "agent context limit",
    "agent validation failed",
    "agent invalid action",
    "task limit reached",
    "unknown",
    "task error",
}
MANIFEST = "sample_manifest.json"
LOG_FILES = {MANIFEST, "runs.jsonl", "error.jsonl", "overall.json"}


def sample_key(index):
    if type(index) not in (int, str):
        raise ValueError("sample indices must be integers or strings")
    return type(index).__name__, index


def validate_indices(indices):
    if not isinstance(indices, list):
        raise TypeError("expected_ids must be a list")
    keys = [sample_key(index) for index in indices]
    if len(set(keys)) != len(keys):
        raise ValueError("expected_ids contains duplicate indices")
    return keys


def save_sample_manifest(directory, indices):
    """Persist the actual get_indices result; refuse changed indices on resume."""
    validate_indices(indices)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / MANIFEST
    value = {"schema_version": 1, "expected_ids": indices}
    if path.exists():
        existing = json.loads(
            path.read_text(encoding="utf-8"), parse_constant=reject_constant
        )
        if (
            not isinstance(existing, dict)
            or type(existing.get("schema_version")) is not int
            or existing["schema_version"] != 1
        ):
            raise ValueError(f"Invalid manifest at {path}")
        validate_indices(existing.get("expected_ids"))
        if existing != value:
            raise ValueError(
                f"Task indices changed since {path} was created; use a new output directory"
            )
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=directory, delete=False
        ) as stream:
            temporary = stream.name
            json.dump(value, stream, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def reject_constant(value):
    raise ValueError(f"non-finite JSON constant: {value}")


def report_task(directory):
    directory = Path(directory)
    diagnostics = []
    expected = None
    manifest_hash = None
    manifest_path = directory / MANIFEST
    if manifest_path.exists():
        try:
            raw = manifest_path.read_bytes()
            manifest_hash = hashlib.sha256(raw).hexdigest()
            manifest = json.loads(raw, parse_constant=reject_constant)
            if (
                not isinstance(manifest, dict)
                or type(manifest.get("schema_version")) is not int
                or manifest["schema_version"] != 1
            ):
                raise ValueError("unsupported manifest schema")
            expected = manifest["expected_ids"]
            validate_indices(expected)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            diagnostics.append({"file": MANIFEST, "message": str(exc)})
            expected = None
    samples = {}
    duplicates = []
    conflicts = []
    for filename in ("runs.jsonl", "error.jsonl"):
        path = directory / filename
        if not path.exists():
            continue
        try:
            with path.open(encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, 1):
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line, parse_constant=reject_constant)
                        if not isinstance(record, dict):
                            raise TypeError("log record must be an object")
                        key = sample_key(record["index"])
                        error = record.get("error")
                        output = record.get("output")
                        if error is not None:
                            if not isinstance(error, str) or not error:
                                raise ValueError(
                                    "error must be a nonempty string or null"
                                )
                        else:
                            if not isinstance(output, dict):
                                raise ValueError("missing TaskOutput")
                            status = output.get("status")
                            if status not in TERMINAL_STATUSES | {"running"}:
                                raise ValueError("unknown TaskOutput status")
                            if (
                                output.get("index") is not None
                                and sample_key(output["index"]) != key
                            ):
                                raise ValueError(
                                    "top-level and TaskOutput indices disagree"
                                )
                        if (filename == "error.jsonl") != (error is not None):
                            raise ValueError("record stored in the wrong log file")
                    except (ValueError, KeyError, TypeError) as exc:
                        diagnostics.append(
                            {"file": filename, "line": line_number, "message": str(exc)}
                        )
                        continue
                    sample = samples.setdefault(
                        key,
                        {
                            "index": record["index"],
                            "recorded_attempt_count": 0,
                            "infrastructure_error_count": 0,
                            "terminal_status": None,
                        },
                    )
                    sample["recorded_attempt_count"] += 1
                    if error is not None:
                        sample["infrastructure_error_count"] += 1
                    elif status in TERMINAL_STATUSES:
                        output_digest = hashlib.sha256(
                            json.dumps(output, sort_keys=True).encode()
                        ).hexdigest()
                        if "first_output_digest" in sample:
                            duplicates.append(record["index"])
                            if output_digest != sample["first_output_digest"]:
                                conflicts.append(record["index"])
                        else:
                            # Same first valid terminal record policy as assigner resume.
                            sample["first_output_digest"] = output_digest
                            sample["terminal_status"] = status
        except (OSError, UnicodeError) as exc:
            diagnostics.append({"file": filename, "message": str(exc)})
    expected_keys = None if expected is None else set(validate_indices(expected))
    completed_keys = {
        key for key, sample in samples.items() if sample["terminal_status"] is not None
    }
    unexpected = (
        []
        if expected_keys is None
        else [s["index"] for key, s in samples.items() if key not in expected_keys]
    )
    completed = (
        completed_keys if expected_keys is None else completed_keys & expected_keys
    )
    pending = (
        None
        if expected is None
        else [i for i in expected if sample_key(i) not in completed]
    )
    infra_pending = [
        s["index"]
        for key, s in samples.items()
        if s["infrastructure_error_count"]
        and key not in completed_keys
        and (expected_keys is None or key in expected_keys)
    ]
    overall_exists = (directory / "overall.json").is_file()
    if overall_exists:
        try:
            overall = json.loads(
                (directory / "overall.json").read_text(encoding="utf-8"),
                parse_constant=reject_constant,
            )
            if not isinstance(overall, dict):
                raise TypeError("overall must be an object")
        except (ValueError, TypeError, OSError) as exc:
            diagnostics.append({"file": "overall.json", "message": str(exc)})
    complete = (
        None
        if expected is None
        else not pending and not unexpected and not conflicts and not diagnostics
    )
    if not overall_exists:
        score_status = "missing_overall"
    elif expected is None:
        score_status = "unknown_coverage"
    elif diagnostics or conflicts or unexpected:
        score_status = "inconsistent_logs"
    elif not complete:
        score_status = "incomplete"
    else:
        score_status = "complete"
    return {
        "directory": str(directory.resolve()),
        "agent": directory.parent.name,
        "task": directory.name,
        "manifest_sha256": manifest_hash,
        "expected_ids": expected,
        "expected_count": None if expected is None else len(expected),
        "terminal_count": len(completed),
        "coverage_fraction": None if not expected else len(completed) / len(expected),
        "pending_ids": pending,
        "infrastructure_error_ids": infra_pending,
        "unexpected_ids": unexpected,
        "duplicate_terminal_ids": duplicates,
        "conflicting_terminal_ids": conflicts,
        "diagnostics": diagnostics,
        "is_complete": complete,
        "overall_exists": overall_exists,
        "score_status": score_status,
        "samples": [
            {k: v for k, v in sample.items() if k != "first_output_digest"}
            for sample in samples.values()
        ],
    }


def analyze_coverage(output):
    tasks = []
    for root, _, files in os.walk(output):
        if LOG_FILES.intersection(files):
            tasks.append(report_task(root))
    return {
        "schema_version": 1,
        "tasks": tasks,
        "attempt_count_note": "Counts valid recorded log entries, including duplicates. NOT_AVAILABLE callbacks are not logged by the legacy assigner. This is not a total execution-attempt count.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", default="outputs")
    parser.add_argument("-s", "--save", default="analysis/coverage.json")
    args = parser.parse_args()
    if not Path(args.output).is_dir():
        parser.error("output directory does not exist")
    report = analyze_coverage(args.output)
    target = Path(args.save)
    # A report must never overwrite a source log, manifest, or benchmark score.
    if target.name in LOG_FILES or target.resolve().is_relative_to(
        Path(args.output).resolve()
    ):
        parser.error("save the coverage report outside the source output directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for task in report["tasks"]:
        denominator = (
            task["expected_count"] if task["expected_count"] is not None else "unknown"
        )
        print(
            f"{task['agent']} {task['task']}: {task['terminal_count']} of {denominator} terminal; {task['score_status']}"
        )
    print(f"Coverage report saved to {target}")


if __name__ == "__main__":
    main()
