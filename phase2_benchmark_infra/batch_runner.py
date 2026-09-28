# batch_runner.py
"""Phase 2 batch runner: point it at a folder of .vrp files and get a
CSV of results, with no per-instance code.

    python batch_runner.py benchmarks/
    python batch_runner.py benchmarks/ --no-verify --out results/run2.csv

Adding a new instance to the dataset means: drop the .vrp file into the
folder and add one entry to fleet_manifest.json. Nothing in this file
changes. This is the Phase 2 acceptance criterion "batch run without
editing code per instance."

Solver settings are NOT redefined here -- they are read from Phase 1's
frozen algorithm_config.json via freeze.load_config(), so a batch run
and a Phase 1 single-instance run are guaranteed to use the identical
solver behavior. Phase 2 owns none of the solving logic, only the
harness around it.
"""

import argparse
import json
import platform
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PHASE1_DIR = HERE.parent / "phase1_freeze"
sys.path.insert(0, str(PHASE1_DIR))
sys.path.insert(0, str(PHASE1_DIR / "core"))
sys.path.insert(0, str(HERE))

import freeze                              # noqa: E402  (Phase 1's frozen tooling)
from cvrp_solver import solve_cvrp         # noqa: E402  (Phase 1's frozen solver)
from validator import validate_solution    # noqa: E402  (Phase 1's frozen validator)
from instance_loader import load_instance, discover_vrp_files  # noqa: E402
from result_schema import ResultRow, write_csv  # noqa: E402

# Timeout tiers by instance size, matching PLAN.md's Phase 4 table.
# These only cap wall-clock as a safety net -- the actual stop rule is
# still solution_limit (Phase 1). A run that hits its tier's cap before
# reaching solution_limit is flagged stop_reason="time_cap" and must be
# excluded from any "frozen result" comparison.
SIZE_TIERS = [
    (50, "tiny", 60),
    (100, "small", 120),
    (250, "medium", 300),
    (500, "large", 600),
    (1000, "stress", 1200),
]


def size_tier(n_customers: int):
    for max_n, label, cap_s in SIZE_TIERS:
        if n_customers < max_n:
            return label, cap_s
    return "stress", SIZE_TIERS[-1][2]


def load_fleet_manifest() -> dict:
    with open(HERE / "fleet_manifest.json", encoding="utf-8") as f:
        return json.load(f)["instances"]


def run_batch(vrp_dir: Path, verify_determinism: bool, run_id: str) -> list:
    cfg = freeze.load_config()
    fleet = load_fleet_manifest()
    fid = freeze.freeze_id()
    machine = freeze.machine_info()
    rows = []

    for vrp_path in discover_vrp_files(vrp_dir):
        name = vrp_path.name
        if name not in fleet:
            print(f"SKIP {name}: no entry in fleet_manifest.json "
                  f"(max_vehicles must be provided, never guessed)")
            continue

        loaded = load_instance(vrp_path)
        instance = loaded.instance
        max_vehicles = fleet[name]["max_vehicles"]
        n_customers = len(instance.customer_ids)
        tier_label, cap_s = size_tier(n_customers)

        run_cfg = json.loads(json.dumps(cfg))  # deep copy
        run_cfg["stopping"]["safety_time_cap_s"] = cap_s

        sol = solve_cvrp(instance, max_vehicles, run_cfg, track_anytime=False)
        report = validate_solution(instance, sol)

        rerun_identical = None
        if verify_determinism:
            sol2 = solve_cvrp(instance, max_vehicles, run_cfg, track_anytime=False)
            rerun_identical = (
                sol.total_distance == sol2.total_distance and
                freeze.route_fingerprint(sol.routes) == freeze.route_fingerprint(sol2.routes))

        gap = None
        if loaded.reference_cost:
            gap = round((sol.total_distance - loaded.reference_cost) / loaded.reference_cost * 100, 4)

        notes = f"size_tier={tier_label}"
        if sol.stop_reason == "time_cap":
            notes += "; WARNING stop_reason=time_cap, NOT a frozen-comparable result"

        row = ResultRow(
            instance=instance.name, nodes=instance.dimension, vehicles=sol.vehicles_used,
            capacity=instance.capacity, reference_cost=loaded.reference_cost,
            reference_source=loaded.reference_source, our_cost=sol.total_distance,
            gap_percent=gap, status=sol.status, feasible=report.overall_pass,
            rerun_identical=rerun_identical, runtime_sec=round(sol.runtime_s, 3),
            solution_count_limit=cfg["stopping"]["solution_limit"], random_seed=None,
            ortools_version=cfg["engine_version_required"], solver_version=cfg["algorithm_version"],
            run_id=run_id, machine_id=machine,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            freeze_id=fid, notes=notes,
        )
        rows.append(row)

        status_flag = "OK" if report.overall_pass else "VALIDATION FAILED"
        print(f"{instance.name:14s} nodes={n_customers:4d} tier={tier_label:6s} "
              f"cost={sol.total_distance:6.0f} gap={gap if gap is not None else '?':>7} "
              f"feasible={report.overall_pass} rerun_identical={rerun_identical} "
              f"t={sol.runtime_s:.1f}s [{status_flag}]")

    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vrp_dir", type=Path, nargs="?", default=HERE / "benchmarks")
    ap.add_argument("--out", type=Path, default=HERE / "results" / "phase2_results.csv")
    ap.add_argument("--no-verify", action="store_true",
                     help="skip the double-run determinism check (faster on large batches)")
    args = ap.parse_args()

    run_id = uuid.uuid4().hex[:8]
    print(f"batch run_id={run_id}  dataset={args.vrp_dir}\n")

    rows = run_batch(args.vrp_dir, verify_determinism=not args.no_verify, run_id=run_id)
    if not rows:
        print("\nNo instances run (check fleet_manifest.json coverage).")
        return 1

    write_csv(rows, args.out)
    n_fail = sum(1 for r in rows if not r.feasible)
    print(f"\nwrote {args.out}  ({len(rows)} instances, {n_fail} infeasible)")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
