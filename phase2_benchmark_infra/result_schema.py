# result_schema.py
"""Locked CSV schema for every benchmark run from Phase 2 onward.

Locking this now matters because Phase 4's benchmark tables and the
Slide data pack (Phase 16 of PLAN.md) both read straight from this
column set -- changing field names later would break every script and
chart built on top of it. Add columns if a later phase needs one; don't
rename or remove existing ones.
"""

import csv
from dataclasses import dataclass, fields
from pathlib import Path
from typing import List, Optional

FIELDNAMES = [
    "instance", "nodes", "vehicles", "capacity",
    "reference_cost", "reference_source", "our_cost", "gap_percent",
    "status", "feasible", "rerun_identical",
    "runtime_sec", "solution_count_limit", "random_seed",
    "ortools_version", "solver_version",
    "run_id", "machine_id", "timestamp", "freeze_id", "notes",
]


@dataclass
class ResultRow:
    instance: str
    nodes: int
    vehicles: int
    capacity: int
    reference_cost: Optional[float]
    reference_source: str
    our_cost: float
    gap_percent: Optional[float]
    status: str
    feasible: bool
    rerun_identical: Optional[bool]
    runtime_sec: float
    solution_count_limit: int
    random_seed: Optional[int]
    ortools_version: str
    solver_version: str
    run_id: str
    machine_id: str
    timestamp: str
    freeze_id: str
    notes: str = ""

    def to_dict(self) -> dict:
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        assert set(d.keys()) == set(FIELDNAMES), (
            "ResultRow fields drifted from FIELDNAMES -- update both together")
        return d


def write_csv(rows: List[ResultRow], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for row in rows:
            w.writerow(row.to_dict())


def append_csv(rows: List[ResultRow], path: Path) -> None:
    """Adds rows to an existing results file (or creates it), for
    batch runs against a growing dataset across multiple invocations."""
    path = Path(path)
    exists = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not exists:
            w.writeheader()
        for row in rows:
            w.writerow(row.to_dict())
