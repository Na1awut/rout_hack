# run_limit_sweep.py
"""Experiment B: the question every earlier phase deferred --
"is solution_limit = 2000 enough?" -- answered with a controlled
sweep instead of a guess.

Three instances, one from each of small/medium/large tiers, each run
at solution_limit in {200, 500, 1000, 2000}, all under the same
per-run safety cap. For each (instance, limit) pair we record the
Gap at that limit AND whether the run actually reached that limit
before the safety cap cut it off -- a limit that was never reached is
not evidence about that limit, it is evidence about the cap.

This produces the "diminishing returns" table PLAN.md's Phase 4 section
asked for, e.g.:

    Limit | Gap  | Runtime
    500   | 2.4% | 4s
    1000  | 1.1% | 8s
    2000  | 0.5% | 15s

except with our own real numbers, not the illustrative ones from the
plan.
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
import freeze                             # noqa: E402

INSTANCES = ["E-n51-k5.vrp", "X-n162-k11.vrp", "X-n459-k26.vrp"]
LIMITS = [200, 500, 1000, 2000]
SAFETY_CAP_S = 90


def main():
    cfg = freeze.load_config()
    cfg["stopping"]["safety_time_cap_s"] = SAFETY_CAP_S

    with open(HERE / "bks_manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)["instances"]

    rows = []
    print(f"Experiment B: solution_limit sweep, safety_cap={SAFETY_CAP_S}s per run\n")
    for filename in INSTANCES:
        meta = manifest[filename]
        instance = parse_vrp_file(str(HERE / "benchmarks" / filename))
        bks = meta["best_known_cost"]
        print(f"-- {instance.name} (n={meta['customers']}, bks={bks}) --")

        for limit in LIMITS:
            run_cfg = json.loads(json.dumps(cfg))
            run_cfg["stopping"]["solution_limit"] = limit

            t0 = time.perf_counter()
            sol = solve_cvrp(instance, meta["max_vehicles"], run_cfg, track_anytime=False)
            wall = time.perf_counter() - t0
            gap = round((sol.total_distance - bks) / bks * 100, 3) if sol.total_distance else None
            reached = sol.stop_reason == "solution_limit"

            rows.append({
                "instance": instance.name, "customers": meta["customers"],
                "solution_limit": limit, "gap_percent": gap,
                "runtime_sec": round(wall, 2), "reached_limit": reached,
                "stop_reason": sol.stop_reason,
            })
            print(f"    limit={limit:5d}  gap={gap:6.2f}%  t={wall:6.2f}s  "
                  f"reached_limit={reached}  stop={sol.stop_reason}")
        print()

    out = HERE / "results" / "experiment_b_limit_sweep.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
