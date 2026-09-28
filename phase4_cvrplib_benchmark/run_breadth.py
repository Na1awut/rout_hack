# run_breadth.py
"""Experiment A (breadth): run every instance under a FIXED wall-clock
budget and see how Gap and "did we even reach solution_limit" change as
instance size grows.

This uses a fixed cap (not the growing per-tier caps Phase 2 used) on
purpose: the question here is "what can the frozen solver achieve in the
same amount of compute time, as the problem gets bigger", which is the
Instance-Size-vs-Gap and Instance-Size-vs-Runtime curves PLAN.md's
Phase 4 section asks for. A growing cap would hide how much size alone
degrades quality; a fixed cap exposes it directly.

solution_limit stays at the Phase 1 frozen value (2000) throughout --
this experiment does NOT tune it. Whether 2000 is reachable at all, and
whether it's overkill or not enough, is Experiment B's job
(run_limit_sweep.py). Here we just record, per instance, whether the
run reached solution_limit before the fixed cap (stop_reason) or was
cut off by it (stop_reason="time_cap") -- a cut-off run is flagged and
is NOT a frozen-comparable result (same rule as Phase 1/2).
"""

import csv
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PHASE1_DIR = HERE.parent / "phase1_freeze"
sys.path.insert(0, str(PHASE1_DIR / "core"))
sys.path.insert(0, str(PHASE1_DIR))

from vrp_parser import parse_vrp_file    # noqa: E402
from cvrp_solver import solve_cvrp       # noqa: E402
from validator import validate_solution  # noqa: E402
import freeze                             # noqa: E402

FIXED_CAP_S = 30


def main():
    cfg = freeze.load_config()
    cfg["stopping"]["safety_time_cap_s"] = FIXED_CAP_S

    with open(HERE / "bks_manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)["instances"]

    rows = []
    print(f"Experiment A: fixed {FIXED_CAP_S}s budget per instance, solution_limit={cfg['stopping']['solution_limit']}\n")
    for filename, meta in sorted(manifest.items(), key=lambda kv: kv[1]["customers"]):
        path = HERE / "benchmarks" / filename
        instance = parse_vrp_file(str(path))
        t0 = time.perf_counter()
        sol = solve_cvrp(instance, meta["max_vehicles"], cfg, track_anytime=False)
        wall = time.perf_counter() - t0
        report = validate_solution(instance, sol)

        bks = meta["best_known_cost"]
        gap = round((sol.total_distance - bks) / bks * 100, 3) if sol.total_distance else None

        row = {
            "instance": instance.name, "tier": meta["tier"], "customers": meta["customers"],
            "vehicles": meta["max_vehicles"], "capacity": meta["capacity"],
            "bks": bks, "proven_optimal": meta["proven_optimal"],
            "our_cost": sol.total_distance, "gap_percent": gap,
            "feasible": report.overall_pass, "status": sol.status,
            "stop_reason": sol.stop_reason, "runtime_sec": round(wall, 2),
            "reached_solution_limit": sol.stop_reason == "solution_limit",
        }
        rows.append(row)
        gap_str = f"{gap:6.2f}%" if gap is not None else "  N/A "
        print(f"{instance.name:14s} n={meta['customers']:4d} tier={meta['tier']:6s} "
              f"cost={sol.total_distance:7.0f} bks={bks:7.0f} gap={gap_str} "
              f"feasible={report.overall_pass} stop={sol.stop_reason:14s} t={wall:5.1f}s")

    out = HERE / "results" / "experiment_a_breadth.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
