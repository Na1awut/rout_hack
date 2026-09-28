# e3_feasibility.py
"""E3: fix weakness W2 -- the 4 instances where v1.0 found NO feasible
solution in 30 s.

E2 showed no OR-Tools first-solution strategy fixes it while the fleet is
pinned to exactly the number of routes in the best-known solution. Two
candidate fixes are tested here, each under the same 30 s budget:

  1. ELASTIC fleet: let the solver use as many vehicles as it needs
     (the X benchmark itself does not fix the fleet -- its BKS for
     X-n599-k92 uses 93 routes, one more than the "k" in the name), and
     report how many it used versus the best-known solution.
  2. A different engine (PyVRP / HGS) that handles capacity violations
     with penalties during search instead of refusing to build a route.
"""
import csv

from common import load, gap, RESULTS
from engines import ortools, pyvrp_hgs
from validator import validate_solution

INSTANCES = ["X-n344-k43", "X-n393-k38", "X-n599-k92", "X-n936-k151"]
BUDGET_S = 30


def main():
    rows = []
    for name in INSTANCES:
        inst, meta = load(name)
        k, n, bks = meta["max_vehicles"], meta["customers"], meta["best_known_cost"]
        print(f"-- {name} (n={n}, bks routes={k}, bks={bks})")
        configs = [
            ("ortools_PCA_elastic", lambda: ortools(inst, n, strategy="PATH_CHEAPEST_ARC", cap_s=BUDGET_S)),
            ("ortools_SAVINGS_elastic", lambda: ortools(inst, n, strategy="SAVINGS", cap_s=BUDGET_S)),
            ("pyvrp_fixed_fleet", lambda: pyvrp_hgs(inst, k, runtime_s=BUDGET_S)),
            ("pyvrp_elastic", lambda: pyvrp_hgs(inst, n, runtime_s=BUDGET_S)),
        ]
        for label, run in configs:
            s = run()
            ok = validate_solution(inst, s).overall_pass if s.routes else False
            g = gap(s.total_distance, bks) if ok else None
            rows.append({"instance": name, "config": label, "feasible": ok,
                         "cost": s.total_distance if ok else "", "gap_percent": "" if g is None else g,
                         "vehicles_used": s.vehicles_used if ok else "", "bks_routes": k,
                         "seconds": round(s.runtime_s, 2)})
            print(f"   {label:26s} feasible={str(ok):5s} gap={'-' if g is None else f'{g:6.2f}%':>8} "
                  f"vehicles={s.vehicles_used if ok else '-'} (bks {k}) t={s.runtime_s:5.1f}s")
    with open(RESULTS / "e3_feasibility.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
