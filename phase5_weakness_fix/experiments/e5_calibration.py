# e5_calibration.py
"""E5: how should a DETERMINISTIC (iteration-based) budget for HGS scale
with instance size, and is HGS actually deterministic at scale?

Part 1 -- cost of one HGS iteration versus n. If seconds-per-iteration
grows roughly linearly with n, a CONSTANT iteration count automatically
gives a size-proportional time budget (the literature's convention,
e.g. Vidal 2022: 4 min per 100 customers) while staying deterministic.

Part 2 -- determinism on a large instance: same seed + same iteration
count, run twice on an idle CPU and once with the CPU deliberately
loaded. Pass = identical route set all three times (Phase 1's test,
now on 458 customers instead of 40).
"""
import csv
import multiprocessing as mp
import os
import time

from common import load, gap, RESULTS
from engines import pyvrp_hgs

CAL_INSTANCES = ["E-n51-k5", "X-n106-k14", "X-n214-k11", "X-n459-k26", "X-n801-k40"]
DET_INSTANCE = "X-n459-k26"
DET_ITERS = 3000


def _burn():
    while True:
        pass


def fingerprint(sol):
    return hash(tuple(sorted(tuple(r.node_ids) for r in sol.routes)))


def main():
    rows = []
    print("Part 1: seconds per HGS iteration vs n (MaxIterations 1000)")
    for name in CAL_INSTANCES:
        inst, meta = load(name)
        s = pyvrp_hgs(inst, meta["max_vehicles"], iterations=1000, seed=1)
        per_iter_ms = s.runtime_s / 1000 * 1000
        n = meta["customers"]
        rows.append({"part": "calibration", "instance": name, "customers": n,
                     "iterations": 1000, "seconds": round(s.runtime_s, 2),
                     "ms_per_iteration": round(per_iter_ms, 3),
                     "ms_per_iteration_per_customer": round(per_iter_ms / n, 5),
                     "gap_percent": gap(s.total_distance, meta["best_known_cost"])})
        print(f"   {name:12s} n={n:4d} t={s.runtime_s:6.2f}s  {per_iter_ms:7.3f} ms/iter  "
              f"{per_iter_ms / n:.5f} ms/iter/customer  gap={gap(s.total_distance, meta['best_known_cost'])}%")

    print(f"\nPart 2: determinism on {DET_INSTANCE}, MaxIterations {DET_ITERS}, seed 1")
    inst, meta = load(DET_INSTANCE)
    k = meta["max_vehicles"]
    a = pyvrp_hgs(inst, k, iterations=DET_ITERS, seed=1)
    b = pyvrp_hgs(inst, k, iterations=DET_ITERS, seed=1)
    hogs = [mp.Process(target=_burn, daemon=True) for _ in range(os.cpu_count() * 2)]
    for h in hogs:
        h.start()
    try:
        c = pyvrp_hgs(inst, k, iterations=DET_ITERS, seed=1)
    finally:
        for h in hogs:
            h.terminate()
    for label, s in [("idle run 1", a), ("idle run 2", b), ("loaded CPU", c)]:
        same = fingerprint(s) == fingerprint(a)
        print(f"   {label:11s} cost={s.total_distance} same_routes_as_run1={same} t={s.runtime_s:.1f}s")
        rows.append({"part": "determinism", "instance": DET_INSTANCE, "customers": meta["customers"],
                     "iterations": DET_ITERS, "seconds": round(s.runtime_s, 2),
                     "ms_per_iteration": "", "ms_per_iteration_per_customer": "",
                     "gap_percent": gap(s.total_distance, meta["best_known_cost"]),
                     "note": f"{label}; same_routes_as_run1={same}"})

    with open(RESULTS / "e5_calibration.csv", "w", newline="", encoding="utf-8") as f:
        fields = list(rows[0]) + ["note"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
