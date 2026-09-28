# engines.py
"""Two engines behind one interface, both returning the frozen core's
CVRPSolution so the SAME validator.py checks both.

- ortools(...)  : the frozen CORE-CVRP v1.0 solve_cvrp, only the config
                  copy differs (strategy / stop / fleet size).
- pyvrp_hgs(...): PyVRP's Hybrid Genetic Search. The instance is NOT read
                  through pyvrp.read(); every edge is inserted from the
                  frozen core's own distance matrix (floor(d + 0.5)), so
                  both engines optimise exactly the same numbers and a
                  cost difference can only come from the search itself.
"""
import json
import time

from common import freeze
from cvrp_solver import solve_cvrp, CVRPSolution, Route
from distance import build_distance_matrix


def ortools(instance, max_vehicles, *, strategy="PATH_CHEAPEST_ARC",
            solution_limit=2000, cap_s=30):
    cfg = json.loads(json.dumps(freeze.load_config()))
    cfg["search"]["first_solution_strategy"] = strategy
    cfg["stopping"]["solution_limit"] = solution_limit
    cfg["stopping"]["safety_time_cap_s"] = cap_s
    return solve_cvrp(instance, max_vehicles, cfg)


def pyvrp_hgs(instance, max_vehicles, *, runtime_s=None, iterations=None, seed=1,
              no_improvement=None):
    """Stop rule: `runtime_s` (wall clock, NOT deterministic), or
    `iterations` (deterministic), optionally combined with
    `no_improvement` = stop after that many iterations without a better
    solution (also counted in iterations, so still deterministic)."""
    from pyvrp import Model
    from pyvrp.stop import MaxRuntime, MaxIterations, NoImprovement, MultipleCriteria

    order = [instance.depot_id] + instance.customer_ids
    D = build_distance_matrix(instance.coords, order)

    m = Model()
    locs = [m.add_location(*instance.coords[nid]) for nid in order]
    m.add_depot(locs[0])
    for loc, nid in zip(locs[1:], order[1:]):
        m.add_client(loc, delivery=[instance.demands[nid]])
    m.add_vehicle_type(num_available=max_vehicles, capacity=[instance.capacity])
    for i, a in enumerate(locs):
        for j, b in enumerate(locs):
            if i != j:
                m.add_edge(a, b, distance=D[i][j])

    if iterations and no_improvement:
        stop = MultipleCriteria([MaxIterations(iterations), NoImprovement(no_improvement)])
    elif iterations:
        stop = MaxIterations(iterations)
    else:
        stop = MaxRuntime(runtime_s)
    t0 = time.perf_counter()
    res = m.solve(stop=stop, seed=seed, display=False)
    runtime = time.perf_counter() - t0
    pyvrp_hgs.last_iterations = res.num_iterations

    best = res.best
    if not best.is_feasible():
        return CVRPSolution(instance.name, [], 0, 0, max_vehicles, "INFEASIBLE",
                            stop_reason="no_feasible", runtime_s=runtime)

    idx = {nid: i for i, nid in enumerate(order)}
    routes, total = [], 0
    for v, r in enumerate(best.routes()):
        # PyVRP 0.14: a route iterates over scheduled activities; a client
        # activity's idx is its 0-based position among clients, i.e. order[1 + idx].
        clients = [order[1 + a.idx] for a in r if a.is_client()]
        nodes = [order[0]] + clients + [order[0]]
        dist = sum(D[idx[a]][idx[b]] for a, b in zip(nodes, nodes[1:]))
        routes.append(Route(v, nodes, sum(instance.demands[n] for n in nodes[1:-1]), dist))
        total += dist
    return CVRPSolution(instance.name, routes, total, len(routes), max_vehicles, "FEASIBLE",
                        stop_reason="iterations" if iterations else "runtime",
                        runtime_s=runtime)
