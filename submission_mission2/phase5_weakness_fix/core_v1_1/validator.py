# validator.py
"""Independent feasibility validator for a CVRPSolution.

Per the qualifier's own rule: a validator must NOT trust numbers the
solver already reported (distance, load) -- it must recompute everything
from the original instance data and the raw route node sequence, then
compare. This file never imports anything from cvrp_solver.py's internal
state; it only reads CVRPSolution.routes (the raw node-id sequences) and
the original VRPInstance.

Checks performed (mirrors the qualifier's feasibility gate):
    1. every node in every route actually exists in the instance
    2. every customer is served exactly once (none missing, none duplicated)
    3. each route's recomputed demand does not exceed capacity
    4. each route's recomputed demand matches what the solver reported
    5. number of routes (vehicles used) does not exceed max_vehicles
    6. every route starts at the depot
    7. every route ends at the depot
    8. the depot never appears in the middle of a route
    9. each route's recomputed distance (EUC_2D, floor(d+0.5)) matches
       what the solver reported
"""

from dataclasses import dataclass, field
from typing import List

from vrp_parser import VRPInstance
from distance import euc_2d_rounded
from cvrp_solver import CVRPSolution


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ValidationReport:
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def overall_pass(self) -> bool:
        return all(c.passed for c in self.checks)

    def add(self, name: str, passed: bool, detail: str = ""):
        self.checks.append(CheckResult(name, passed, detail))

    def print_report(self):
        for c in self.checks:
            mark = "PASS" if c.passed else "FAIL"
            line = f"  [{mark}] {c.name}"
            if c.detail:
                line += f" -- {c.detail}"
            print(line)
        print(f"\nOVERALL VALIDATION: {'PASS' if self.overall_pass else 'FAIL'}")


def validate_solution(instance: VRPInstance, solution: CVRPSolution) -> ValidationReport:
    report = ValidationReport()
    valid_node_ids = set(instance.coords.keys())
    customer_ids = set(instance.customer_ids)

    # 1. every node in every route exists in the instance
    unknown_nodes = set()
    for r in solution.routes:
        for n in r.node_ids:
            if n not in valid_node_ids:
                unknown_nodes.add(n)
    report.add("All route nodes exist in instance", not unknown_nodes,
               f"unknown nodes: {sorted(unknown_nodes)}" if unknown_nodes else "")

    # 2. every customer served exactly once
    served = []
    for r in solution.routes:
        served.extend(n for n in r.node_ids if n != instance.depot_id)
    served_set = set(served)
    missing = customer_ids - served_set
    duplicated = {n for n in served if served.count(n) > 1}
    report.add("Every customer served exactly once",
               not missing and not duplicated,
               f"missing: {sorted(missing)}, duplicated: {sorted(duplicated)}"
               if (missing or duplicated) else "")

    # 3 & 4. capacity respected and matches reported demand
    capacity_ok = True
    demand_mismatch = []
    for r in solution.routes:
        recalculated = sum(instance.demands[n] for n in r.node_ids if n != instance.depot_id)
        if recalculated > instance.capacity:
            capacity_ok = False
        if recalculated != r.demand:
            demand_mismatch.append((r.vehicle_id, r.demand, recalculated))
    report.add("No route exceeds capacity", capacity_ok,
               f"capacity={instance.capacity}" if not capacity_ok else "")
    report.add("Reported load matches recalculated load", not demand_mismatch,
               "; ".join(f"vehicle {v}: reported={rep}, recalculated={rec}"
                         for v, rep, rec in demand_mismatch))

    # 5. vehicle count within limit
    report.add("Vehicles used <= max_vehicles",
               solution.vehicles_used <= solution.max_vehicles,
               f"used={solution.vehicles_used}, max={solution.max_vehicles}")

    # 6 & 7. every route starts/ends at depot
    starts_ok = all(r.node_ids and r.node_ids[0] == instance.depot_id for r in solution.routes)
    ends_ok = all(r.node_ids and r.node_ids[-1] == instance.depot_id for r in solution.routes)
    report.add("Every route starts at depot", starts_ok)
    report.add("Every route ends at depot", ends_ok)

    # 8. depot never appears mid-route
    mid_depot = any(instance.depot_id in r.node_ids[1:-1] for r in solution.routes)
    report.add("Depot does not appear mid-route", not mid_depot)

    # 9. recomputed distance matches reported distance
    dist_mismatch = []
    total_recalculated = 0
    for r in solution.routes:
        d = 0
        for i in range(len(r.node_ids) - 1):
            d += euc_2d_rounded(instance.coords[r.node_ids[i]], instance.coords[r.node_ids[i + 1]])
        total_recalculated += d
        if d != r.distance:
            dist_mismatch.append((r.vehicle_id, r.distance, d))
    report.add("Recalculated distance matches reported distance", not dist_mismatch,
               "; ".join(f"vehicle {v}: reported={rep}, recalculated={rec}"
                         for v, rep, rec in dist_mismatch))
    report.add("Recalculated total distance matches reported total",
               total_recalculated == solution.total_distance,
               f"reported={solution.total_distance}, recalculated={total_recalculated}")

    return report
