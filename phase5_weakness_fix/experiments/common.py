# common.py -- shared paths and loaders for Phase 5 experiments.
import json
import sys
from pathlib import Path

PHASE5 = Path(__file__).resolve().parent.parent
ROOT = PHASE5.parent
PHASE1 = ROOT / "phase1_freeze"
PHASE4 = ROOT / "phase4_cvrplib_benchmark"
BENCH = PHASE4 / "benchmarks"
RESULTS = PHASE5 / "results"

sys.path.insert(0, str(PHASE1 / "core"))
sys.path.insert(0, str(PHASE1))

import freeze                                   # noqa: E402
from vrp_parser import parse_vrp_file           # noqa: E402


def bks_manifest() -> dict:
    with open(PHASE4 / "bks_manifest.json", encoding="utf-8") as f:
        return json.load(f)["instances"]


def load(name: str):
    """name without .vrp -> (instance, manifest entry)"""
    return parse_vrp_file(str(BENCH / f"{name}.vrp")), bks_manifest()[f"{name}.vrp"]


def gap(cost, bks):
    return None if not cost else round((cost - bks) / bks * 100, 3)
