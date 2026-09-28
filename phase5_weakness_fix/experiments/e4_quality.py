# e4_quality.py
"""E4: fix weakness W3 (gap grows to 8-17 % on medium/large instances).

Same instances, same fleet rule as Phase 4 (fleet fixed to the BKS route
count), and the SAME wall-clock budget for every engine on a given
instance: max(10 s, 0.1 s per customer). A size-proportional budget is
the standard used in the literature (Vidal 2022: 4 min per 100
customers); ours is scaled down 40x to fit a working session.

Compared:
  - ortools_v1.0      : frozen CORE-CVRP v1.0 (PATH_CHEAPEST_ARC + GLS)
  - ortools_SAVINGS   : same, Clarke & Wright first solution (E2 winner)
  - pyvrp_hgs         : Hybrid Genetic Search, same distance matrix
"""
import csv

from common import load, gap, RESULTS
from engines import ortools, pyvrp_hgs
from validator import validate_solution

INSTANCES = ["E-n51-k5", "E-n76-k10", "X-n106-k14", "X-n162-k11", "X-n214-k11",
             "X-n298-k31", "X-n344-k43", "X-n459-k26", "X-n599-k92", "X-n801-k40"]


def budget(n):
    return max(10, round(0.1 * n))


def main():
    rows = []
    for name in INSTANCES:
        inst, meta = load(name)
        k, n, bks = meta["max_vehicles"], meta["customers"], meta["best_known_cost"]
        b = budget(n)
        print(f"-- {name} (n={n}, k={k}, bks={bks}, budget={b}s)")
        configs = [
            ("ortools_v1.0", lambda: ortools(inst, k, strategy="PATH_CHEAPEST_ARC",
                                             solution_limit=10**9, cap_s=b)),
            ("ortools_SAVINGS", lambda: ortools(inst, k, strategy="SAVINGS",
                                                solution_limit=10**9, cap_s=b)),
            ("pyvrp_hgs", lambda: pyvrp_hgs(inst, k, runtime_s=b)),
        ]
        for label, run in configs:
            s = run()
            ok = validate_solution(inst, s).overall_pass if s.routes else False
            g = gap(s.total_distance, bks) if ok else None
            rows.append({"instance": name, "customers": n, "budget_s": b, "config": label,
                         "feasible": ok, "cost": s.total_distance if ok else "",
                         "gap_percent": "" if g is None else g, "seconds": round(s.runtime_s, 2)})
            print(f"   {label:16s} feasible={str(ok):5s} gap={'-' if g is None else f'{g:6.2f}%':>8} t={s.runtime_s:5.1f}s")
    with open(RESULTS / "e4_quality.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
