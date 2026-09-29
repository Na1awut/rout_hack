"""Mission 2 benchmark: solve A-n32-k5, B-n31-k5, P-n40-k5 with CORE-CVRP v1.1.

    python run_benchmark.py

Writes results/benchmark/summary.csv and one CVRPLIB-style .sol per instance
(routes list customer numbers as in CVRPLIB: node id - 1, depot omitted).
Also checks each run against the regression snapshot recorded in Phase 6.
"""
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "phase5_weakness_fix" / "core_v1_1"))
sys.path.insert(0, str(ROOT / "phase5_weakness_fix"))
import freeze                                   # noqa: E402
from cvrp_solver import solve_cvrp              # noqa: E402
from validator import validate_solution         # noqa: E402
from vrp_parser import parse_vrp_file           # noqa: E402

BENCH = ROOT / "phase1_freeze" / "benchmarks"
OUT = ROOT / "results" / "benchmark"


def main():
    cfg = freeze.load_config()                  # refuses any pyvrp version other than 0.14.0
    ref = json.loads((ROOT / "phase1_freeze" / "reference_bks.json").read_text())["instances"]
    snap = json.loads((ROOT / "phase6_readymix_simulation/loop_00_regression_lock/snapshot.json").read_text())["instances"]
    OUT.mkdir(parents=True, exist_ok=True)
    rows, ok_all = [], True
    print(f"CORE-CVRP {cfg['algorithm_version']} · pyvrp {freeze.engine_version()} · seed {cfg['search']['seed']} · "
          f"stop: {cfg['stopping']['no_improvement_iterations']} no-improvement iters (cap {cfg['stopping']['max_iterations']})\n")
    for name in ("A-n32-k5", "B-n31-k5", "P-n40-k5"):
        meta = ref[name + ".vrp"]
        inst = parse_vrp_file(str(BENCH / (name + ".vrp")))
        t0 = time.perf_counter()
        sol = solve_cvrp(inst, meta["max_vehicles"], cfg)
        wall = time.perf_counter() - t0
        rep = validate_solution(inst, sol)
        gap = (sol.total_distance - meta["bks"]) / meta["bks"] * 100
        fp = freeze.route_fingerprint(sol.routes)
        matches = fp == snap[name]["fingerprint"] and sol.total_distance == snap[name]["cost"]
        ok_all &= rep.overall_pass and matches
        routes = sorted(r.node_ids for r in sol.routes)
        with open(OUT / f"{name}.sol", "w") as f:
            for i, r in enumerate(routes, 1):
                f.write(f"Route #{i}: " + " ".join(str(n - 1) for n in r[1:-1]) + "\n")
            f.write(f"Cost {sol.total_distance}\n")
        rows.append(dict(instance=name, customers=len(inst.customer_ids), vehicles_allowed=meta["max_vehicles"],
                         vehicles_used=sol.vehicles_used, status=sol.status, cost=sol.total_distance,
                         optimal_reference=meta["bks"], gap_percent=round(gap, 4), validator_pass=rep.overall_pass,
                         iterations=sol.iterations, stop_reason=sol.stop_reason, seed=cfg["search"]["seed"],
                         runtime_s=round(wall, 2), route_fingerprint=fp, matches_phase6_snapshot=matches))
        print(f"{name:10s} cost {sol.total_distance:4d}  optimal {meta['bks']:4d}  gap {gap:6.2f}%  "
              f"vehicles {sol.vehicles_used}/{meta['max_vehicles']}  valid {rep.overall_pass}  "
              f"snapshot {'match' if matches else 'DIFF'}  {wall:.1f}s")
        for i, r in enumerate(routes, 1):
            print(f"   Route #{i}: " + " ".join(str(n - 1) for n in r[1:-1]))
    with open(OUT / "summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {OUT / 'summary.csv'} and .sol files · all valid and match snapshot: {ok_all}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
