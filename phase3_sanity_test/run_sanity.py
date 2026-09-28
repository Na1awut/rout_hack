# run_sanity.py
"""Phase 3 acceptance test: does the frozen solver actually get simple,
hand-verifiable cases right?

This intentionally does NOT trust validator.py alone, even though it is
already independent of the solver (Phase 1) -- a bug in the validator
itself would then go unnoticed by every later phase. So every structural
check below (visit-once, capacity, depot start/end, distance) is
re-implemented here in a few plain lines, deliberately not by importing
validator.py's logic. If this file and validator.py ever disagree about
whether a solution is valid, that disagreement is itself the finding to
chase down -- see PHASE3.md's "double-check" note.

For the 5 FEASIBLE instances, the check is exact equality against a
hand-derived optimal cost (see generate_sanity_instances.py for how each
number was derived) -- not a Gap, not "close enough."

For the 2 INFEASIBLE instances, the check is that solve_cvrp reports
status == "INFEASIBLE", not a crash and not a silently-wrong feasible
answer.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PHASE1_CORE = HERE.parent / "phase1_freeze" / "core"
PHASE1_DIR = HERE.parent / "phase1_freeze"
sys.path.insert(0, str(PHASE1_CORE))
sys.path.insert(0, str(PHASE1_DIR))

from vrp_parser import parse_vrp_file   # noqa: E402
from cvrp_solver import solve_cvrp      # noqa: E402
import freeze                            # noqa: E402


def independent_checks(instance, solution):
    """Re-derives every structural invariant from scratch, without
    calling validator.py. Returns (ok: bool, problems: list[str])."""
    problems = []
    depot = instance.depot_id
    all_customers = set(instance.customer_ids)

    visited = []
    for route in solution.routes:
        nodes = route.node_ids
        if not nodes or nodes[0] != depot:
            problems.append(f"vehicle {route.vehicle_id}: route does not start at depot")
        if not nodes or nodes[-1] != depot:
            problems.append(f"vehicle {route.vehicle_id}: route does not end at depot")
        middle = nodes[1:-1]
        if depot in middle:
            problems.append(f"vehicle {route.vehicle_id}: depot appears mid-route")
        visited.extend(middle)

        load = sum(instance.demands[n] for n in middle)
        if load > instance.capacity:
            problems.append(f"vehicle {route.vehicle_id}: load {load} > capacity {instance.capacity}")
        if load != route.demand:
            problems.append(f"vehicle {route.vehicle_id}: reported demand {route.demand} "
                             f"!= recomputed {load}")

        recomputed_dist = 0
        for a, b in zip(nodes, nodes[1:]):
            xa, ya = instance.coords[a]
            xb, yb = instance.coords[b]
            import math
            recomputed_dist += math.floor(math.sqrt((xa - xb) ** 2 + (ya - yb) ** 2) + 0.5)
        if recomputed_dist != route.distance:
            problems.append(f"vehicle {route.vehicle_id}: reported distance {route.distance} "
                             f"!= recomputed {recomputed_dist}")

    missing = all_customers - set(visited)
    if missing:
        problems.append(f"customers never visited: {sorted(missing)}")
    duplicates = [c for c in set(visited) if visited.count(c) > 1]
    if duplicates:
        problems.append(f"customers visited more than once: {sorted(duplicates)}")

    return (not problems), problems


def run_feasible_case(cfg, fleet, item) -> bool:
    path = HERE / "instances" / item["file"]
    instance = parse_vrp_file(str(path))
    max_vehicles = fleet[item["file"]]["max_vehicles"]

    sol = solve_cvrp(instance, max_vehicles, cfg, track_anytime=False)
    ok_structural, problems = independent_checks(instance, sol)
    ok_cost = (sol.total_distance == item["expected_cost"])
    ok = ok_structural and ok_cost and sol.status != "INFEASIBLE"

    print(f"[{'PASS' if ok else 'FAIL'}] {instance.name:20s} "
          f"cost={sol.total_distance} expected={item['expected_cost']} "
          f"structural_ok={ok_structural}")
    if not ok_cost:
        print(f"       cost mismatch: {item['derivation']}")
    for p in problems:
        print(f"       PROBLEM: {p}")
    return ok


def run_infeasible_case(cfg, fleet, item) -> bool:
    path = HERE / "instances" / item["file"]
    instance = parse_vrp_file(str(path))
    max_vehicles = fleet[item["file"]]["max_vehicles"]

    sol = solve_cvrp(instance, max_vehicles, cfg, track_anytime=False)
    ok = sol.status == "INFEASIBLE"
    print(f"[{'PASS' if ok else 'FAIL'}] {instance.name:20s} "
          f"status={sol.status} (expected INFEASIBLE)")
    if not ok:
        print(f"       PROBLEM: solver did not report INFEASIBLE for an unroutable instance "
              f"-- this is a correctness bug, not a quality issue")
    return ok


def main():
    cfg = freeze.load_config()
    with open(HERE / "expected_results.json", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(HERE / "fleet_manifest.json", encoding="utf-8") as f:
        fleet = json.load(f)["instances"]

    print(f"CORE-CVRP {cfg['algorithm_version']}  freeze_id={freeze.freeze_id()}\n")

    print("-- feasible cases (exact hand-derived optimal) --")
    feasible_ok = all(run_feasible_case(cfg, fleet, item) for item in manifest["feasible"])

    print("\n-- infeasible cases (must be correctly rejected) --")
    infeasible_ok = all(run_infeasible_case(cfg, fleet, item) for item in manifest["infeasible"])

    print(f"\nPHASE 3 SANITY TEST: {'PASS' if feasible_ok and infeasible_ok else 'FAIL'}")
    return 0 if feasible_ok and infeasible_ok else 1


if __name__ == "__main__":
    sys.exit(main())
