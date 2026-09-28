# generate_sanity_instances.py
"""Builds tiny, hand-verifiable .vrp files for Phase 3.

Every instance here places customers on a single straight line
(y = 0) with integer x-coordinates. That is not a simplification for
convenience only -- it removes rounding entirely from the correctness
check: EUC_2D distance between two points on the same horizontal line
is sqrt(dx^2 + 0^2) = |dx| exactly, and floor(|dx| + 0.5) = |dx| for
any integer dx. So every distance in these instances is an exact
integer that anyone can recompute with a calculator, with zero
disagreement possible between "the formula" and "what a human adds up."

Two families are generated:

1. SINGLE-VEHICLE LINE instances (n = 5, 10, 20, 30 customers).
   max_vehicles = 1, capacity set far above total demand, so there is
   only one truck and it must visit every customer once and return.
   For points on a line, the optimal round trip that visits all of
   them is unambiguous: drive to the farthest point and back, passing
   every other point on the way. Its cost is exactly 2 * max(x).
   This is not an approximation or a guess -- it is the textbook result
   for a single-vehicle open interval TSP, and it is what Phase 3 checks
   the frozen solver's reported distance against, at increasing n, to
   see whether correctness holds as the instance grows (not whether the
   solver is fast or optimal on harder combinatorial structure -- that
   is Phase 4's job).

2. FORCED-TWO-VEHICLE CLUSTER instance (n = 4).
   Two customers near the depot (x=10, 11) and two customers far away
   (x=1000, 1001), demand=10 each, capacity=20 (so each truck can take
   at most 2). With exactly 4 customers and a cap of 2 per truck, a
   2-truck solution must split them into two pairs of two -- there are
   only 3 distinct ways to pair 4 items, and this module's docstring
   enumerates all 3 by hand in PHASE3.md, so we know 2024 is the true
   minimum, not just "the intuitive one." This is the one sanity
   instance whose expected answer required checking every option
   instead of an interval-TSP formula.

3. INFEASIBLE instances -- a single customer whose demand exceeds a
   single truck's capacity (unroutable at all), and a demand total
   that exceeds every truck's combined capacity (routable individually,
   not all together). The solver must report INFEASIBLE for both, not
   silently drop a customer or ignore capacity.

Output files use the identical CVRPLIB text format already accepted by
vrp_parser.py (Phase 1) -- COMMENT carries "Optimal value: N" so these
flow through instance_loader.py (Phase 2) exactly like a downloaded
benchmark, with no special-casing anywhere in the pipeline.
"""

from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "instances"


def _write_vrp(path: Path, name: str, capacity: int, coords: dict, demands: dict,
               depot_id: int, comment: str):
    lines = [
        f"NAME : {name}",
        f"COMMENT : ({comment})",
        "TYPE : CVRP",
        f"DIMENSION : {len(coords)}",
        "EDGE_WEIGHT_TYPE : EUC_2D",
        f"CAPACITY : {capacity}",
        "NODE_COORD_SECTION",
    ]
    for node_id, (x, y) in sorted(coords.items()):
        lines.append(f" {node_id} {x} {y}")
    lines.append("DEMAND_SECTION")
    for node_id, d in sorted(demands.items()):
        lines.append(f" {node_id} {d}")
    lines.append("DEPOT_SECTION")
    lines.append(f" {depot_id}")
    lines.append(" -1")
    lines.append("EOF")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_single_vehicle_line(n_customers: int) -> dict:
    """Customers at x = 10, 20, 30, ... on y=0. Depot at (0,0). Demand
    is small and uniform so total demand is always far under capacity
    -- the point of this instance is testing route correctness with
    exactly one vehicle, not capacity splitting."""
    coords = {1: (0, 0)}
    demands = {1: 0}
    for i in range(1, n_customers + 1):
        node_id = i + 1
        coords[node_id] = (i * 10, 0)
        demands[node_id] = 1
    max_x = n_customers * 10
    expected_cost = 2 * max_x
    name = f"LINE-n{n_customers}-k1"
    _write_vrp(
        OUT_DIR / f"{name}.vrp", name, capacity=1000, coords=coords, demands=demands,
        depot_id=1, comment=f"Sanity, hand-derived optimal: single vehicle round trip "
                             f"on a line = 2 * max(x) = 2 * {max_x}, No of trucks: 1, "
                             f"Optimal value: {expected_cost}")
    return {"file": f"{name}.vrp", "max_vehicles": 1, "expected_cost": expected_cost,
            "derivation": f"2 * max(x) = 2 * {max_x} = {expected_cost} (single-vehicle "
                           f"line TSP: drive to the farthest point and back)"}


def build_forced_two_vehicle_cluster() -> dict:
    """4 customers, 2 clusters of 2 (near: x=10,11 ; far: x=1000,1001),
    demand=10 each, capacity=20 (max 2 per truck), max_vehicles=2.
    Every one of the 3 possible pairings is enumerated in PHASE3.md;
    the near+near / far+far pairing (cost 2024) is the unique minimum.
    """
    coords = {1: (0, 0), 2: (10, 0), 3: (11, 0), 4: (1000, 0), 5: (1001, 0)}
    demands = {1: 0, 2: 10, 3: 10, 4: 10, 5: 10}
    name = "CLUSTER-n4-k2"
    _write_vrp(
        OUT_DIR / f"{name}.vrp", name, capacity=20, coords=coords, demands=demands,
        depot_id=1, comment="Sanity, hand-enumerated optimal over all 3 pairings, "
                             "No of trucks: 2, Optimal value: 2024")
    return {"file": f"{name}.vrp", "max_vehicles": 2, "expected_cost": 2024,
            "derivation": "enumerated all 3 pairings of {10,11,1000,1001} into two "
                           "pairs of 2: near+near/far+far=2024, near+far/near+far (two "
                           "ways)=4002 each. Minimum is 2024."}


def build_infeasible_single_customer_too_heavy():
    coords = {1: (0, 0), 2: (10, 0)}
    demands = {1: 0, 2: 200}
    name = "INFEASIBLE-single-overweight"
    _write_vrp(
        OUT_DIR / f"{name}.vrp", name, capacity=100, coords=coords, demands=demands,
        depot_id=1, comment="Sanity: customer 2 demand=200 > capacity=100, "
                             "no truck can ever carry it. Must be INFEASIBLE.")
    return {"file": f"{name}.vrp", "max_vehicles": 3}


def build_infeasible_total_demand_exceeds_fleet():
    """3 customers, demand=40 each (120 total), capacity=50, 2 trucks
    (fleet capacity 100). Each customer fits alone in a truck, but the
    fleet cannot carry all 3 at once (120 > 100)."""
    coords = {1: (0, 0), 2: (10, 0), 3: (20, 0), 4: (30, 0)}
    demands = {1: 0, 2: 40, 3: 40, 4: 40}
    name = "INFEASIBLE-fleet-capacity"
    _write_vrp(
        OUT_DIR / f"{name}.vrp", name, capacity=50, coords=coords, demands=demands,
        depot_id=1, comment="Sanity: 3 customers x demand=40 = 120 total, but "
                             "2 trucks x capacity=50 = 100 fleet capacity. "
                             "Each customer is individually routable, but not all "
                             "3 together. Must be INFEASIBLE.")
    return {"file": f"{name}.vrp", "max_vehicles": 2}


def main():
    OUT_DIR.mkdir(exist_ok=True)
    manifest = {"feasible": [], "infeasible": []}
    for n in (5, 10, 20, 30):
        manifest["feasible"].append(build_single_vehicle_line(n))
    manifest["feasible"].append(build_forced_two_vehicle_cluster())
    manifest["infeasible"].append(build_infeasible_single_customer_too_heavy())
    manifest["infeasible"].append(build_infeasible_total_demand_exceeds_fleet())

    import json
    with open(Path(__file__).resolve().parent / "expected_results.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"wrote {len(manifest['feasible'])} feasible + {len(manifest['infeasible'])} "
          f"infeasible instances to {OUT_DIR}")


if __name__ == "__main__":
    main()
