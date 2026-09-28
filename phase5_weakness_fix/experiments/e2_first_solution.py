# e2_first_solution.py
"""E2: can a different first-solution strategy fix the 4 instances where
CORE-CVRP v1.0 (PATH_CHEAPEST_ARC) found NO feasible solution in 30 s?

Only the FIRST solution is requested (solution_limit=1), so this measures
construction alone -- time to a first feasible plan and its cost --
without any local search mixing in. Uses the frozen v1.0 solve_cvrp
unchanged; only the strategy name in a copied config differs.
"""
import csv
import json
import time

from common import freeze, load, gap, RESULTS
from cvrp_solver import solve_cvrp
from validator import validate_solution

INSTANCES = [
    # the 4 no-solution instances from Phase 4
    "X-n344-k43", "X-n393-k38", "X-n599-k92", "X-n936-k151",
    # the 2 worst-gap feasible instances, as a control
    "X-n214-k11", "X-n298-k31",
]
STRATEGIES = [
    "PATH_CHEAPEST_ARC",            # v1.0 baseline
    "SAVINGS",                      # Clarke & Wright (1964)
    "PARALLEL_CHEAPEST_INSERTION",
    "LOCAL_CHEAPEST_INSERTION",
    "CHRISTOFIDES",
    "AUTOMATIC",
]
CAP_S = 30


def main():
    base = freeze.load_config()
    rows = []
    for name in INSTANCES:
        inst, meta = load(name)
        print(f"-- {name} (n={meta['customers']}, k={meta['max_vehicles']}, bks={meta['best_known_cost']})")
        for strat in STRATEGIES:
            cfg = json.loads(json.dumps(base))
            cfg["search"]["first_solution_strategy"] = strat
            cfg["stopping"]["solution_limit"] = 1
            cfg["stopping"]["safety_time_cap_s"] = CAP_S
            t0 = time.perf_counter()
            sol = solve_cvrp(inst, meta["max_vehicles"], cfg)
            t = time.perf_counter() - t0
            ok = validate_solution(inst, sol).overall_pass if sol.routes else False
            g = gap(sol.total_distance, meta["best_known_cost"]) if ok else None
            rows.append({"instance": name, "strategy": strat, "feasible": ok,
                         "first_cost": sol.total_distance if ok else "",
                         "gap_percent": g if g is not None else "",
                         "seconds": round(t, 2)})
            print(f"   {strat:28s} feasible={str(ok):5s} gap={g if g is not None else '-':>8} t={t:6.2f}s")
    out = RESULTS / "e2_first_solution.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
