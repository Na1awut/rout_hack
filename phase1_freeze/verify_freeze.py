# verify_freeze.py
"""Phase 1 acceptance test for the frozen CORE-CVRP v1.0.

For every instance in reference_bks.json:
  1. run the frozen solver twice from scratch,
  2. check both runs give the same cost AND the same route set,
  3. check the answer is feasible with the independent validator,
  4. compute Gap vs. the frozen reference and the anytime score.
Then one extra run of the largest instance with the CPU deliberately
loaded, to show the result does not depend on machine speed.

Writes results/phase1_results.csv; every row carries the freeze_id.

Usage:
    python verify_freeze.py            # full check incl. loaded-CPU run
    python verify_freeze.py --no-load  # skip the loaded-CPU run (faster)
"""

import csv
import multiprocessing as mp
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "core"))
sys.path.insert(0, str(HERE))

from vrp_parser import parse_vrp_file          # noqa: E402
from cvrp_solver import solve_cvrp             # noqa: E402
from validator import validate_solution        # noqa: E402
import freeze                                  # noqa: E402

LOADED_CHECK_INSTANCE = "P-n40-k5.vrp"


def run_once(filename, max_vehicles, cfg):
    inst = parse_vrp_file(str(freeze.BENCH_DIR / filename))
    sol = solve_cvrp(inst, max_vehicles, cfg, track_anytime=True)
    report = validate_solution(inst, sol)
    return inst, sol, report


def _burn():
    while True:
        pass


def main():
    do_load = "--no-load" not in sys.argv
    cfg = freeze.load_config()
    ref = freeze.load_reference()
    fid = freeze.freeze_id()
    limit = cfg["stopping"]["solution_limit"]
    print(f"CORE-CVRP {cfg['algorithm_version']}  freeze_id={fid}  "
          f"stop=solution_limit {limit}")
    print(f"machine: {freeze.machine_info()}\n")

    rows = []
    all_ok = True
    for filename, meta in ref["instances"].items():
        k, bks = meta["max_vehicles"], meta["bks"]
        inst, s1, rep1 = run_once(filename, k, cfg)
        _, s2, _ = run_once(filename, k, cfg)

        fp1, fp2 = freeze.route_fingerprint(s1.routes), freeze.route_fingerprint(s2.routes)
        reproducible = (s1.total_distance == s2.total_distance) and (fp1 == fp2)
        frozen_stop = s1.stop_reason == "solution_limit" and s2.stop_reason == "solution_limit"
        gap = (s1.total_distance - bks) / bks * 100
        score = freeze.anytime_score(s1.anytime.points, bks, limit)
        ok = rep1.overall_pass and reproducible and frozen_stop
        all_ok &= ok

        print(f"{inst.name:10s} cost={s1.total_distance:4d} bks={bks:4d} gap={gap:5.2f}% "
              f"anytime={score:.4f} feasible={rep1.overall_pass} "
              f"rerun_identical={reproducible} stop={s1.stop_reason} "
              f"t={s1.runtime_s:.1f}s/{s2.runtime_s:.1f}s  routes={fp1}")

        rows.append({
            "freeze_id": fid, "instance": inst.name, "customers": len(inst.customer_ids),
            "max_vehicles": k, "vehicles_used": s1.vehicles_used, "bks": bks,
            "cost": s1.total_distance, "gap_pct": round(gap, 4),
            "anytime_score": round(score, 6),
            "first_solution_cost": s1.anytime.points[0].cost if s1.anytime.points else "",
            "solution_index_of_best": s1.anytime.points[-1].solution_index if s1.anytime.points else "",
            "feasible": rep1.overall_pass, "rerun_identical": reproducible,
            "stop_reason": s1.stop_reason, "runtime_s_run1": round(s1.runtime_s, 3),
            "runtime_s_run2": round(s2.runtime_s, 3), "route_fingerprint": fp1,
            "condition": "idle", "machine": freeze.machine_info(),
        })

    if do_load:
        filename = LOADED_CHECK_INSTANCE
        meta = ref["instances"][filename]
        hogs = [mp.Process(target=_burn, daemon=True) for _ in range(os.cpu_count() * 2)]
        for h in hogs:
            h.start()
        try:
            inst, s, rep = run_once(filename, meta["max_vehicles"], cfg)
        finally:
            for h in hogs:
                h.terminate()
        idle_fp = next(r["route_fingerprint"] for r in rows if r["instance"] == inst.name)
        fp = freeze.route_fingerprint(s.routes)
        same = fp == idle_fp
        all_ok &= same and rep.overall_pass
        print(f"\n[loaded CPU] {inst.name} cost={s.total_distance} routes={fp} "
              f"same_as_idle={same} stop={s.stop_reason} t={s.runtime_s:.1f}s")
        rows.append({
            "freeze_id": fid, "instance": inst.name, "customers": len(inst.customer_ids),
            "max_vehicles": meta["max_vehicles"], "vehicles_used": s.vehicles_used,
            "bks": meta["bks"], "cost": s.total_distance,
            "gap_pct": round((s.total_distance - meta["bks"]) / meta["bks"] * 100, 4),
            "anytime_score": round(freeze.anytime_score(s.anytime.points, meta["bks"], limit), 6),
            "first_solution_cost": s.anytime.points[0].cost if s.anytime.points else "",
            "solution_index_of_best": s.anytime.points[-1].solution_index if s.anytime.points else "",
            "feasible": rep.overall_pass, "rerun_identical": same,
            "stop_reason": s.stop_reason, "runtime_s_run1": round(s.runtime_s, 3),
            "runtime_s_run2": "", "route_fingerprint": fp,
            "condition": f"loaded ({os.cpu_count() * 2} busy processes)",
            "machine": freeze.machine_info(),
        })

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "phase1_results.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {out}")
    print(f"PHASE 1 FREEZE: {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
