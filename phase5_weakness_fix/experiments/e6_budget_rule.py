# e6_budget_rule.py
"""E6: pick the deterministic stop rule for CORE-CVRP v1.1.

Two deterministic families, same 5 instances (50 -> 800 customers):
  - fixed iteration count: 2k / 5k / 10k / 20k
  - adaptive: stop after N iterations with no improvement
    (N = 2k or 5k), with a hard cap of 50k iterations so a run can never
    go on forever.
The adaptive rule spends more iterations only where the search is still
improving -- a hard instance gets more budget, an easy one stops early --
while remaining exactly reproducible (it counts iterations, not seconds).
"""
import csv

from common import load, gap, RESULTS
from engines import pyvrp_hgs

INSTANCES = ["E-n51-k5", "X-n106-k14", "X-n214-k11", "X-n459-k26", "X-n801-k40"]
RULES = [
    ("iter_2000", dict(iterations=2000)),
    ("iter_5000", dict(iterations=5000)),
    ("iter_10000", dict(iterations=10000)),
    ("iter_20000", dict(iterations=20000)),
    ("noimp_2000_cap50k", dict(iterations=50000, no_improvement=2000)),
    ("noimp_5000_cap50k", dict(iterations=50000, no_improvement=5000)),
]


def main():
    rows = []
    for name in INSTANCES:
        inst, meta = load(name)
        print(f"-- {name} (n={meta['customers']})")
        for label, kw in RULES:
            s = pyvrp_hgs(inst, meta["max_vehicles"], seed=1, **kw)
            g = gap(s.total_distance, meta["best_known_cost"]) if s.routes else None
            it = pyvrp_hgs.last_iterations
            rows.append({"instance": name, "customers": meta["customers"], "rule": label,
                         "iterations_used": it, "gap_percent": "" if g is None else g,
                         "seconds": round(s.runtime_s, 2), "feasible": bool(s.routes)})
            print(f"   {label:18s} iters={it:6d} gap={'-' if g is None else f'{g:6.2f}%':>8} t={s.runtime_s:6.1f}s")
    with open(RESULTS / "e6_budget_rule.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
