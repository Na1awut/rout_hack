# capacity_projection.py -- feed a Ready-Mix dataset to the frozen core
"""Capacity-only projection of one day: plant = depot, one CVRP customer
per truckload, demand in 0.25 m3 units, capacity = drum size, one CVRP
vehicle per truckload (a truck doing several trips a day appears as several
CVRP vehicles; time is ignored here).

Because every trip is strictly larger than half a drum, no two trips can
share a route. The projection therefore has exactly one feasible shape
(each trip alone: plant -> site -> plant) and its optimal distance is
known in closed form. That makes it a strong plumbing test -- the core's
answer must equal sum_trips 2 x d(plant, site) exactly -- and it shows
where the real decisions in Ready-Mix are: which truck, when to leave,
in what order. Distance alone is fixed by the orders.

Reads decision-time files only, never ground_truth/.
"""

import csv
import math
from pathlib import Path

from readymix.core import frozen_core as core
from readymix.simulation.common import planar_km

DEMAND_UNIT_M3 = 0.25
COORD_UNIT_KM = 0.1          # EUC_2D distances come out in units of 100 m of road


def _rows(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build_instance(dataset_dir):
    root = Path(dataset_dir)
    plant = _rows(root / "master/plants.csv")[0]
    sites = {s["site_id"]: s for s in _rows(root / "master/sites.csv")}
    trips = _rows(root / "orders/trips.csv")
    cap_m3 = float(_rows(root / "master/vehicles.csv")[0]["capacity_m3"])
    lat0, lon0 = float(plant["latitude"]), float(plant["longitude"])

    # circuity is read back from the traffic table so the projection sees the
    # same road distances the simulator uses
    road = {r["to_node"]: float(r["road_km"]) for r in _rows(root / "runtime/traffic.csv")
            if r["from_node"] == plant["plant_id"]}
    xy, factors = {}, []
    for sid, s in sites.items():
        x, y = planar_km(lat0, lon0, float(s["latitude"]), float(s["longitude"]))
        factors.append(road[sid] / math.hypot(x, y))
        xy[sid] = (x, y)
    circuity = sum(factors) / len(factors)
    if max(factors) - min(factors) > 1e-3:
        raise ValueError("road_km / straight-line km is not constant across sites")

    coords = {1: (0.0, 0.0)}
    demands = {1: 0}
    node_trip = {}
    for i, t in enumerate(trips, start=2):
        x, y = xy[t["site_id"]]
        coords[i] = (x * circuity / COORD_UNIT_KM, y * circuity / COORD_UNIT_KM)
        demands[i] = round(float(t["volume_m3"]) / DEMAND_UNIT_M3)
        node_trip[i] = t["trip_id"]
    inst = core.VRPInstance(name=root.name, dimension=len(coords), capacity=round(cap_m3 / DEMAND_UNIT_M3),
                            coords=coords, demands=demands, depot_id=1, optimal=None, n_trucks_hint=None)
    return inst, node_trip


def solve_projection(dataset_dir) -> dict:
    inst, node_trip = build_instance(dataset_dir)
    cfg = core.load_frozen_config()
    n = len(node_trip)
    sol = core.solve_cvrp(inst, n, cfg)
    report = core.validate_solution(inst, sol) if sol.routes else None
    analytic = sum(2 * core.euc_2d_rounded(inst.coords[1], inst.coords[i]) for i in node_trip)
    customer_demands = [inst.demands[i] for i in node_trip]
    two_smallest = sorted(customer_demands)[:2]
    return {
        "trips": n,
        "pairing_impossible": len(two_smallest) < 2 or sum(two_smallest) > inst.capacity,
        "status": sol.status,
        "validator_pass": bool(report and report.overall_pass),
        "routes": sol.vehicles_used,
        "one_trip_per_route": all(len(r.node_ids) == 3 for r in sol.routes),
        "core_distance_units": sol.total_distance,
        "analytic_distance_units": analytic,
        "matches_analytic": sol.total_distance == analytic,
        "distance_km": round(sol.total_distance * COORD_UNIT_KM, 1),
        "iterations": sol.iterations,
        "runtime_s": round(sol.runtime_s, 3),
    }
