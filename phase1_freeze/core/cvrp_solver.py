# cvrp_solver.py
"""CORE-CVRP v1.0 -- the frozen solver.

Copied from 04_hackathon_qualifier/solver/cvrp_solver.py (same model,
same search strategy) with three Phase-1 changes:

1. Every search setting comes from algorithm_config.json instead of
   function defaults, so the config file IS the algorithm definition.
2. Stopping is work-based (`solution_limit`) instead of wall-clock.
   Measured before this change: P-n40-k5 with a 1.5 s time limit gave
   468 on an idle machine but 478/478/494 on a loaded one; with a
   solution limit it gave 458 every time on both (just slower when
   loaded). The wall-clock limit is kept only as a safety cap; a run
   that hits it is reported as stop_reason="time_cap" and must not be
   treated as a frozen result.
3. `status` no longer claims "OPTIMAL" for ROUTING_SUCCESS. OR-Tools'
   ROUTING_SUCCESS only means a solution was found; proven optimality is
   ROUTING_OPTIMAL, which local search never reports. The old solver in
   04 labelled these runs "OPTIMAL" -- that label was wrong even though
   the costs matched the known optimum.
"""

import time
from dataclasses import dataclass
from typing import List, Optional
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from vrp_parser import VRPInstance
from distance import build_distance_matrix


@dataclass
class Route:
    vehicle_id: int
    node_ids: List[int]      # depot ... depot, using ORIGINAL node ids from the file
    demand: int
    distance: int


@dataclass
class CVRPSolution:
    instance_name: str
    routes: List[Route]       # only non-empty routes (vehicle actually used)
    total_distance: int
    vehicles_used: int
    max_vehicles: int
    status: str                # "OPTIMAL", "FEASIBLE", or "INFEASIBLE"
    stop_reason: str = ""      # "solution_limit", "time_cap", or "search_exhausted"
    runtime_s: float = 0.0
    anytime: Optional[object] = None   # AnytimeTracker, set when track_anytime=True


_STATUS = routing_enums_pb2.RoutingSearchStatus


def solve_cvrp(instance: VRPInstance, max_vehicles: int, config: dict,
               track_anytime: bool = False) -> CVRPSolution:
    search = config["search"]
    stop = config["stopping"]

    node_order = [instance.depot_id] + instance.customer_ids
    dist_matrix = build_distance_matrix(instance.coords, node_order)
    demands = [instance.demands[n] for n in node_order]

    manager = pywrapcp.RoutingIndexManager(len(node_order), max_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_cb(from_index, to_index):
        return dist_matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    transit_index = routing.RegisterTransitCallback(distance_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_index)

    def demand_cb(from_index):
        return demands[manager.IndexToNode(from_index)]

    demand_index = routing.RegisterUnaryTransitCallback(demand_cb)
    routing.AddDimensionWithVehicleCapacity(
        demand_index, 0, [instance.capacity] * max_vehicles, True, "Capacity")

    tracker = None
    if track_anytime:
        from anytime_tracker import AnytimeTracker
        tracker = AnytimeTracker(routing.solver(), routing)
        routing.AddSearchMonitor(tracker)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = getattr(
        routing_enums_pb2.FirstSolutionStrategy, search["first_solution_strategy"])
    params.local_search_metaheuristic = getattr(
        routing_enums_pb2.LocalSearchMetaheuristic, search["local_search_metaheuristic"])
    params.solution_limit = stop["solution_limit"]
    params.time_limit.FromSeconds(stop["safety_time_cap_s"])

    t0 = time.perf_counter()
    solution = routing.SolveWithParameters(params)
    runtime = time.perf_counter() - t0

    if solution is None:
        return CVRPSolution(instance.name, [], 0, 0, max_vehicles, "INFEASIBLE",
                            stop_reason="no_solution", runtime_s=runtime, anytime=tracker)

    routes: List[Route] = []
    total_distance = 0
    for v in range(max_vehicles):
        index = routing.Start(v)
        if routing.IsEnd(solution.Value(routing.NextVar(index))):
            continue  # unused vehicle
        node_ids, route_demand, route_distance = [], 0, 0
        while True:
            node = manager.IndexToNode(index)
            node_ids.append(node_order[node])
            route_demand += demands[node]
            next_index = solution.Value(routing.NextVar(index))
            route_distance += dist_matrix[node][manager.IndexToNode(next_index)]
            if routing.IsEnd(next_index):
                node_ids.append(node_order[manager.IndexToNode(next_index)])
                break
            index = next_index
        routes.append(Route(v, node_ids, route_demand, route_distance))
        total_distance += route_distance

    status_enum = routing.status()
    status = "OPTIMAL" if status_enum == _STATUS.ROUTING_OPTIMAL else "FEASIBLE"
    if runtime >= stop["safety_time_cap_s"] - 0.5:
        stop_reason = "time_cap"
    elif status_enum == _STATUS.ROUTING_SUCCESS:
        stop_reason = "solution_limit"
    else:
        stop_reason = "search_exhausted"

    return CVRPSolution(instance.name, routes, total_distance, len(routes), max_vehicles,
                        status, stop_reason=stop_reason, runtime_s=runtime, anytime=tracker)
