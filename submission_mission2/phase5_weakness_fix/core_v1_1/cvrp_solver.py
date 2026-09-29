# cvrp_solver.py
"""CORE-CVRP v1.1 -- the Phase 5 solver.

What changed from v1.0 (phase1_freeze/core/cvrp_solver.py), and why --
every point is backed by an experiment in phase5_weakness_fix/:

1. Engine: OR-Tools GLS -> PyVRP Hybrid Genetic Search (HGS).
   E4: equal wall-clock budget on 10 CVRPLIB instances (50-800
   customers): HGS gap 0.00-2.44 %, OR-Tools v1.0 3.1-17.6 % and no
   feasible answer on 2 of them.
2. Stop rule: iteration-counted, seeded -> identical routes on any
   machine, now also on large instances. E5: X-n459-k26 (458 customers),
   two idle runs + one run with the CPU saturated -> same route set all
   three times. v1.0's solution_limit could not be reached on 150+
   customers and fell back to a wall-clock cap (Phase 4).
3. Tight fixed fleets no longer end in "no solution". E3: the 4
   instances where v1.0 found nothing (fleet pinned to the BKS route
   count) are all solved by HGS with the SAME fleet (gap 0.86-3.97 %
   in 30 s). HGS treats capacity overload as a penalty during search
   instead of refusing to build a route.
4. NEW -- fleet diagnosis. If the fixed fleet still has no feasible
   plan, the solver re-solves with an unlimited fleet and reports how
   many vehicles the plan actually needs (`fleet_diagnosis`). Answers
   "how many more trucks do we need?" instead of just "infeasible"
   (PLAN.md Phase 15: the system must say "additional vehicles
   required", not crash).

Unchanged on purpose: the parser, the EUC_2D rounding floor(d + 0.5)
(every edge given to PyVRP comes from distance.build_distance_matrix),
the validator, and the rule that max_vehicles is supplied by the
caller, never inferred from a filename.
"""

import time
from dataclasses import dataclass
from typing import List, Optional

from vrp_parser import VRPInstance
from distance import build_distance_matrix


@dataclass
class Route:
    vehicle_id: int
    node_ids: List[int]      # depot ... depot, ORIGINAL node ids from the file
    demand: int
    distance: int


@dataclass
class FleetDiagnosis:
    fixed_fleet: int
    vehicles_needed: int      # routes used by the best plan found with an unlimited fleet
    extra_vehicles: int       # vehicles_needed - fixed_fleet (>= 1 when the fixed fleet failed)
    elastic_cost: int         # total distance of that unlimited-fleet plan


@dataclass
class CVRPSolution:
    instance_name: str
    routes: List[Route]
    total_distance: int
    vehicles_used: int
    max_vehicles: int
    status: str                # "FEASIBLE" or "INFEASIBLE" (heuristic: never claims OPTIMAL)
    stop_reason: str = ""      # "iteration_limit" | "no_improvement"
    runtime_s: float = 0.0
    iterations: int = 0
    anytime: Optional[list] = None            # [(iteration, best_feasible_cost)]
    fleet_diagnosis: Optional[FleetDiagnosis] = None


def _build_model(instance: VRPInstance, num_vehicles: int):
    from pyvrp import Model
    order = [instance.depot_id] + instance.customer_ids
    D = build_distance_matrix(instance.coords, order)
    m = Model()
    locs = [m.add_location(*instance.coords[nid]) for nid in order]
    m.add_depot(locs[0])
    for loc, nid in zip(locs[1:], order[1:]):
        m.add_client(loc, delivery=[instance.demands[nid]])
    m.add_vehicle_type(num_available=num_vehicles, capacity=[instance.capacity])
    for i, a in enumerate(locs):
        for j, b in enumerate(locs):
            if i != j:
                m.add_edge(a, b, distance=D[i][j])
    return m, order, D


def _stop(config):
    from pyvrp.stop import MaxIterations, NoImprovement, MultipleCriteria
    s = config["stopping"]
    crits = [MaxIterations(s["max_iterations"])]
    if s.get("no_improvement_iterations"):
        crits.append(NoImprovement(s["no_improvement_iterations"]))
    return crits[0] if len(crits) == 1 else MultipleCriteria(crits)


def _run(instance, num_vehicles, config):
    m, order, D = _build_model(instance, num_vehicles)
    t0 = time.perf_counter()
    res = m.solve(stop=_stop(config), seed=config["search"]["seed"],
                  display=False, collect_stats=True)
    runtime = time.perf_counter() - t0

    anytime, best_seen = [], float("inf")
    for i, st in enumerate(res.stats.data):
        if st.best_feas and st.best_cost < best_seen:
            best_seen = st.best_cost
            anytime.append((i + 1, int(st.best_cost)))

    stop_reason = ("iteration_limit" if res.num_iterations >= config["stopping"]["max_iterations"]
                   else "no_improvement")
    best = res.best
    if not best.is_feasible():
        return CVRPSolution(instance.name, [], 0, 0, num_vehicles, "INFEASIBLE",
                            stop_reason, runtime, res.num_iterations, anytime)

    idx = {nid: i for i, nid in enumerate(order)}
    routes, total = [], 0
    for v, r in enumerate(best.routes()):
        clients = [order[1 + a.idx] for a in r if a.is_client()]
        nodes = [order[0]] + clients + [order[0]]
        dist = sum(D[idx[a]][idx[b]] for a, b in zip(nodes, nodes[1:]))
        routes.append(Route(v, nodes, sum(instance.demands[n] for n in clients), dist))
        total += dist
    return CVRPSolution(instance.name, routes, total, len(routes), num_vehicles, "FEASIBLE",
                        stop_reason, runtime, res.num_iterations, anytime)


def solve_cvrp(instance: VRPInstance, max_vehicles: int, config: dict,
               diagnose_fleet: bool = True) -> CVRPSolution:
    """Fixed-fleet solve (the qualifier rule). If no feasible plan is
    found and diagnose_fleet is True, re-solve with one vehicle per
    customer (an effectively unlimited fleet) and attach how many
    vehicles would actually be needed. The returned status stays
    INFEASIBLE for the fixed fleet -- the diagnosis is extra information,
    never a silent substitution of a bigger fleet."""
    sol = _run(instance, max_vehicles, config)
    if sol.status == "INFEASIBLE" and diagnose_fleet:
        elastic = _run(instance, max(1, len(instance.customer_ids)), config)
        if elastic.status == "FEASIBLE":
            sol.fleet_diagnosis = FleetDiagnosis(
                fixed_fleet=max_vehicles, vehicles_needed=elastic.vehicles_used,
                extra_vehicles=elastic.vehicles_used - max_vehicles,
                elastic_cost=elastic.total_distance)
    return sol
