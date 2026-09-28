"""Probe: does the current core give identical results when re-run?
Compares wall-clock stopping (time_limit) vs. count-based stopping (solution_limit)."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from vrp_parser import parse_vrp_file
from distance import build_distance_matrix

BENCH = str(__import__("pathlib").Path(__file__).resolve().parent.parent / "benchmarks")


def run(path, k, time_ms=None, sol_limit=None):
    inst = parse_vrp_file(path)
    order = [inst.depot_id] + inst.customer_ids
    D = build_distance_matrix(inst.coords, order)
    dem = [inst.demands[n] for n in order]
    m = pywrapcp.RoutingIndexManager(len(order), k, 0)
    r = pywrapcp.RoutingModel(m)
    cb = r.RegisterTransitCallback(lambda a, b: D[m.IndexToNode(a)][m.IndexToNode(b)])
    r.SetArcCostEvaluatorOfAllVehicles(cb)
    dc = r.RegisterUnaryTransitCallback(lambda a: dem[m.IndexToNode(a)])
    r.AddDimensionWithVehicleCapacity(dc, 0, [inst.capacity] * k, True, "C")
    p = pywrapcp.DefaultRoutingSearchParameters()
    p.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    p.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    if time_ms:
        p.time_limit.FromMilliseconds(time_ms)
    if sol_limit:
        p.solution_limit = sol_limit
        p.time_limit.FromSeconds(600)
    t0 = time.perf_counter()
    s = r.SolveWithParameters(p)
    el = time.perf_counter() - t0
    # fingerprint of the actual route set, not just cost
    routes = []
    for v in range(k):
        i, rt = r.Start(v), []
        while not r.IsEnd(i):
            rt.append(m.IndexToNode(i)); i = s.Value(r.NextVar(i))
        routes.append(tuple(rt))
    return s.ObjectiveValue(), hash(tuple(sorted(routes))), el


if __name__ == "__main__":
    for name, k, opt in [("A-n32-k5.vrp", 5, 784), ("P-n40-k5.vrp", 5, 458)]:
        path = f"{BENCH}\\{name}"
        for label, kw in [("time 300ms", dict(time_ms=300)),
                          ("time 1500ms", dict(time_ms=1500)),
                          ("solution_limit 2000", dict(sol_limit=2000))]:
            res = [run(path, k, **kw) for _ in range(5)]
            costs = [c for c, _, _ in res]
            fps = {f for _, f, _ in res}
            times = [t for _, _, t in res]
            print(f"{name:14s} {label:22s} costs={costs} distinct_routesets={len(fps)} "
                  f"time={min(times):.2f}-{max(times):.2f}s (opt={opt})")
