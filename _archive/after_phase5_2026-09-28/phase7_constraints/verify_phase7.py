"""Rebuild contract examples, run acceptance checks, and save an audit report."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import platform
import unittest

import build_examples
from contract import input_hash, prepare_case, read_json
from validate_contract import validate_plan

HERE = Path(__file__).resolve().parent


def main():
    spec = importlib.util.spec_from_file_location("frozen_phase5", HERE.parent / "phase5_weakness_fix/freeze.py")
    frozen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(frozen)
    before = frozen.freeze_id()
    expected = read_json(HERE.parent / "phase6_topic_selection/results/gate_summary.json")["core_freeze_id"]
    build_examples.main()
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(HERE), pattern="test_contract.py")
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    output = HERE / "results"
    output.mkdir(exist_ok=True)
    (output / "tests.txt").write_text(stream.getvalue(), encoding="utf-8")
    examples = []
    for name in ("normal", "static", "readiness", "no_work"):
        case = read_json(HERE / "examples" / f"{name}.input.json")
        plan = read_json(HERE / "examples" / f"{name}.output.json")
        validation = validate_plan(case, plan)
        examples.append({"name": name, "input_sha256": input_hash(case),
                         "preparation_status": prepare_case(case)["status"], "validation": validation})
    after = frozen.freeze_id()
    passed = result.wasSuccessful() and all(e["validation"]["valid"] for e in examples) and before == after == expected
    files = sorted(HERE.glob("*.py")) + sorted((HERE / "schemas").glob("*.json"))
    report = {"status": "PASS" if passed else "FAIL", "contract_version": "1.0",
              "python": platform.python_version(), "tests_run": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors),
              "examples": examples, "core_freeze_id_before": before, "core_freeze_id_after": after,
              "expected_core_freeze_id": expected,
              "artifacts": [{"path": p.relative_to(HERE).as_posix(),
                             "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
    build_examples.write(output / "verification.json", report)
    print(f"Phase 7: {report['status']}; {result.testsRun} tests; {len(examples)} example plans; core {after}")
    if not passed:
        print(stream.getvalue())
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
