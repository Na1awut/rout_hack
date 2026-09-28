# verify_v1_1.py
"""Acceptance test for CORE-CVRP v1.1. A new version must pass EVERY gate
the frozen v1.0 passed, then show it fixes the Phase 4 weaknesses:

  Gate 1 (Phase 1 / Mission 2): A-n32-k5, B-n31-k5, P-n40-k5, P-n19-k2
          -> gap 0.00 %, feasible, and a re-run gives the same routes.
  Gate 2 (Phase 3): the 5 hand-derived instances must hit their exact
          cost (checked by phase3's own independent checker, not the
          validator), and the 2 impossible instances must be INFEASIBLE.
          New: the fleet-capacity case must carry a fleet diagnosis
          saying exactly 1 more vehicle is needed.
  Gate 3 (Phase 4): all 24 CVRPLIB instances, side by side with v1.0's
          Phase 4 result. Written to results/v1_1_vs_v1_0.csv.

Usage:  python verify_v1_1.py            (all gates)
        python verify_v1_1.py --skip-24   (gates 1-2 only, fast)
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE / "core_v1_1"))
sys.path.insert(0, str(HERE))

import freeze                                   # noqa: E402  (v1.1 tooling)
from vrp_parser import parse_vrp_file           # noqa: E402
from cvrp_solver import solve_cvrp              # noqa: E402
from validator import validate_solution         # noqa: E402

sys.path.insert(0, str(ROOT / "phase3_sanity_test"))
from run_sanity import independent_checks       # noqa: E402  (phase3's checker, not the validator)


def gate1(cfg):
    print("Gate 1 -- Mission 2 benchmarks (must stay 0.00 %)")
    ref = json.loads((ROOT / "phase1_freeze" / "reference_bks.json").read_text(encoding="utf-8"))
    ok_all = True
    for fname, meta in ref["instances"].items():
        inst = parse_vrp_file(str(ROOT / "phase1_freeze" / "benchmarks" / fname))
        a = solve_cvrp(inst, meta["max_vehicles"], cfg)
        b = solve_cvrp(inst, meta["max_vehicles"], cfg)
        same = freeze.route_fingerprint(a.routes) == freeze.route_fingerprint(b.routes)
        valid = validate_solution(inst, a).overall_pass
        g = (a.total_distance - meta["bks"]) / meta["bks"] * 100
        ok = valid and same and abs(g) < 1e-9
        ok_all &= ok
        print(f"   [{'PASS' if ok else 'FAIL'}] {inst.name:10s} cost={a.total_distance} bks={meta['bks']} "
              f"gap={g:.2f}% rerun_identical={same} iters={a.iterations} t={a.runtime_s:.2f}s")
    return ok_all


def gate2(cfg):
    print("\nGate 2 -- Phase 3 hand-derived sanity instances")
    d = ROOT / "phase3_sanity_test"
    exp = json.loads((d / "expected_results.json").read_text(encoding="utf-8"))
    fleet = json.loads((d / "fleet_manifest.json").read_text(encoding="utf-8"))["instances"]
    ok_all = True
    for item in exp["feasible"]:
        inst = parse_vrp_file(str(d / "instances" / item["file"]))
        s = solve_cvrp(inst, fleet[item["file"]]["max_vehicles"], cfg)
        structural, problems = independent_checks(inst, s)
        ok = structural and s.total_distance == item["expected_cost"]
        ok_all &= ok
        print(f"   [{'PASS' if ok else 'FAIL'}] {inst.name:28s} cost={s.total_distance} expected={item['expected_cost']}")
        for p in problems:
            print(f"          PROBLEM: {p}")
    for item in exp["infeasible"]:
        inst = parse_vrp_file(str(d / "instances" / item["file"]))
        s = solve_cvrp(inst, fleet[item["file"]]["max_vehicles"], cfg)
        diag = s.fleet_diagnosis
        if "fleet-capacity" in item["file"]:
            ok = s.status == "INFEASIBLE" and diag is not None and diag.extra_vehicles == 1
            note = f"diagnosis: needs {diag.vehicles_needed} vehicles (+{diag.extra_vehicles})" if diag else "no diagnosis"
        else:
            ok = s.status == "INFEASIBLE" and diag is None
            note = "no fleet size can fix it (single customer heavier than a truck)" if diag is None else "unexpected diagnosis"
        ok_all &= ok
        print(f"   [{'PASS' if ok else 'FAIL'}] {inst.name:28s} status={s.status}  {note}")
    return ok_all


def gate3(cfg, fid):
    print("\nGate 3 -- Phase 4 CVRPLIB set, v1.1 vs v1.0")
    d = ROOT / "phase4_cvrplib_benchmark"
    manifest = json.loads((d / "bks_manifest.json").read_text(encoding="utf-8"))["instances"]
    v10 = {r["instance"]: r for r in csv.DictReader(open(d / "results" / "experiment_a_breadth.csv", encoding="utf-8"))}
    horizon = cfg["stopping"]["max_iterations"]
    rows = []
    for fname, meta in sorted(manifest.items(), key=lambda kv: kv[1]["customers"]):
        inst = parse_vrp_file(str(d / "benchmarks" / fname))
        s = solve_cvrp(inst, meta["max_vehicles"], cfg)
        valid = validate_solution(inst, s).overall_pass if s.routes else False
        bks = meta["best_known_cost"]
        g = round((s.total_distance - bks) / bks * 100, 3) if valid else None
        old = v10[inst.name]
        old_gap = old["gap_percent"] or "no solution"
        rows.append({"freeze_id": fid, "instance": inst.name, "customers": meta["customers"],
                     "vehicles": meta["max_vehicles"], "bks": bks, "proven_optimal": meta["proven_optimal"],
                     "v1_0_gap_percent": old["gap_percent"], "v1_0_stop": old["stop_reason"],
                     "v1_1_cost": s.total_distance if valid else "", "v1_1_gap_percent": "" if g is None else g,
                     "v1_1_feasible": valid, "v1_1_iterations": s.iterations, "v1_1_stop": s.stop_reason,
                     "v1_1_runtime_s": round(s.runtime_s, 2),
                     "v1_1_anytime_score": round(freeze.anytime_score(s.anytime or [], bks, horizon), 6),
                     "machine": freeze.machine_info()})
        print(f"   {inst.name:12s} n={meta['customers']:4d}  v1.0 gap={old_gap:>12}  ->  v1.1 gap="
              f"{'-' if g is None else f'{g:6.2f}%':>8} iters={s.iterations:6d} t={s.runtime_s:6.1f}s")
    out = HERE / "results" / "v1_1_vs_v1_0.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"   wrote {out}")
    return all(r["v1_1_feasible"] for r in rows)


def main():
    cfg = freeze.load_config()
    fid = freeze.freeze_id()
    print(f"CORE-CVRP {cfg['algorithm_version']}  freeze_id={fid}  engine=pyvrp {freeze.engine_version()}")
    print(f"machine: {freeze.machine_info()}\n")
    ok = gate1(cfg) and gate2(cfg)
    if "--skip-24" not in sys.argv:
        ok = gate3(cfg, fid) and ok
    print(f"\nCORE-CVRP v1.1 ACCEPTANCE: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
