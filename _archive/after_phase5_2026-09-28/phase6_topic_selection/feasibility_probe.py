"""Phase 6 decision gate, not the production application.

36 synthetic components -> 12 indivisible delivery batches -> 4 sites.
Uses frozen CORE-CVRP v1.1 for the capacity-only projection and the same
installed PyVRP 0.14.0 engine for a separate fixed-slot VRPTW adapter.
No routes or objective values are hard-coded. All operational data are
simulation assumptions. Run: python phase6_topic_selection/feasibility_probe.py
"""
from __future__ import annotations

import copy
import csv
import hashlib
import importlib
import inspect
import json
import math
import platform
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(ROOT / "phase5_weakness_fix"),
                str(ROOT / "phase5_weakness_fix" / "core_v1_1")]
import freeze
from cvrp_solver import solve_cvrp
from validator import validate_solution
from vrp_parser import parse_vrp_file
from pyvrp import Model
from pyvrp.stop import MaxIterations, MultipleCriteria, NoImprovement


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate_case():
    # CPAC leaflet p2 supports the product families and 100/120 mm thicknesses.
    # These lengths, widths and density are OUR assumptions, not CPAC specs.
    families = {
        "wall_100": {"length_m": 2.8, "width_m": 2.4, "thickness_m": .10},
        "floor_120": {"length_m": 3.0, "width_m": 1.2, "thickness_m": .12},
    }
    sites = [(10000, 4000), (16000, 6000), (-10000, 5000), (-16000, 8000)]
    components, jobs = [], []
    for s, coord in enumerate(sites):
        for wave in range(3):
            jid = f"S{s + 1}-B{wave + 1}"
            parts = []
            for k in range(3):
                family = "floor_120" if (wave + k) % 3 == 1 else "wall_100"
                dims = families[family]
                weight = math.ceil(math.prod(dims.values()) * 2400)
                component = {"component_id": f"{jid}-C{k + 1}", "job_id": jid,
                             "site": f"S{s + 1}", "family": family, **dims,
                             "density_kg_m3_assumed": 2400, "weight_kg": weight,
                             "installation_rank": wave * 3 + k + 1,
                             "production_ready_min": 420,
                             "mass_source": "assumed geometry x assumed density",
                             "thickness_source": "CPAC leaflet p2"}
                parts.append(component)
                components.append(component)
            slot_start = 540 + wave * 120 + (40 if s % 2 else 0)
            jobs.append({"job_id": jid, "site": f"S{s + 1}", "coord_m": coord,
                         "component_ids": [c["component_id"] for c in parts],
                         "weight_kg": sum(c["weight_kg"] for c in parts),
                         "sequence": wave + 1, "service_min": 24,
                         "slot_start": slot_start, "slot_end": slot_start + 36,
                         "release_min": 420, "site_ready_min": 420,
                         "production_ready": True, "site_ready": True,
                         "load_plan_approved_assumption": True})
    return {"label": "SYNTHETIC - no CPAC operational data", "units": {
                "coordinates": "metres in a fictional planar map", "time": "minutes after midnight",
                "mass": "kg", "distance": "rounded Euclidean metres"},
            "depot_coord_m": [0, 0], "fleet_size": 6, "capacity_kg": 9000,
            "shift_start": 420, "shift_end": 1020, "families": families,
            "components": components, "jobs": jobs}


def eligibility(case):
    eligible, deferred = [], []
    blocked_sites = set()
    for job in sorted(case["jobs"], key=lambda j: (j["site"], j["sequence"])):
        reasons = []
        if not job["production_ready"]:
            reasons.append("production_not_ready")
        if not job["site_ready"]:
            reasons.append("site_not_ready")
        if job["site"] in blocked_sites:
            reasons.append("predecessor_deferred")
        if reasons:
            blocked_sites.add(job["site"])
            deferred.append({"job_id": job["job_id"], "reasons": reasons,
                             "components": len(job["component_ids"])})
        else:
            eligible.append(job)
    return eligible, deferred


def precheck(case, jobs):
    if any(j["weight_kg"] > case["capacity_kg"] for j in jobs):
        return "PROVEN_INFEASIBLE_BATCH_CAPACITY"
    if sum(j["weight_kg"] for j in jobs) > case["fleet_size"] * case["capacity_kg"]:
        return "PROVEN_INFEASIBLE_FLEET_CAPACITY_SINGLE_TRIP"
    by_site = {}
    for j in jobs:
        if not j["load_plan_approved_assumption"]:
            return "INPUT_REQUIRES_LOAD_PLAN"
        if j["slot_end"] - max(j["slot_start"], j["site_ready_min"]) < j["service_min"]:
            return "PROVEN_INFEASIBLE_SERVICE_SLOT"
        by_site.setdefault(j["site"], []).append(j)
    for js in by_site.values():
        js.sort(key=lambda j: j["sequence"])
        if any(a["slot_end"] > b["slot_start"] for a, b in zip(js, js[1:])):
            # Overlapping windows may be solvable with a scheduler. This adapter
            # cannot certify arbitrary precedence, so it rejects the input.
            return "UNSUPPORTED_OVERLAPPING_SEQUENCE_SLOTS"
    return "ACCEPTED"


def distance(a, b):
    return math.floor(math.hypot(a[0] - b[0], a[1] - b[1]) + .5)


def vrp_projection(case, jobs, path):
    coords = [case["depot_coord_m"]] + [j["coord_m"] for j in jobs]
    lines = ["NAME : PRECASTFLOW-SYNTHETIC", "TYPE : CVRP", f"DIMENSION : {len(coords)}",
             "EDGE_WEIGHT_TYPE : EUC_2D", f"CAPACITY : {case['capacity_kg']}", "NODE_COORD_SECTION"]
    lines += [f"{i + 1} {p[0]} {p[1]}" for i, p in enumerate(coords)]
    lines += ["DEMAND_SECTION", "1 0"]
    lines += [f"{i + 2} {j['weight_kg']}" for i, j in enumerate(jobs)]
    lines += ["DEPOT_SECTION", "1", "-1", "EOF"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return parse_vrp_file(str(path))


def solve_slots(case, jobs, seed):
    problem = precheck(case, jobs)
    if problem != "ACCEPTED":
        return {"status": problem, "routes": []}
    m = Model()
    dep = m.add_location(*case["depot_coord_m"])
    m.add_depot(dep)
    locations = [dep]
    for j in jobs:
        loc = m.add_location(*j["coord_m"])
        locations.append(loc)
        m.add_client(loc, delivery=[j["weight_kg"]], service_duration=j["service_min"],
                     tw_early=max(j["slot_start"], j["site_ready_min"]),
                     tw_late=j["slot_end"] - j["service_min"],
                     release_time=j["release_min"], name=j["job_id"])
    m.add_vehicle_type(num_available=case["fleet_size"], capacity=[case["capacity_kg"]],
                       tw_early=case["shift_start"], tw_late=case["shift_end"])
    for a in locations:
        for b in locations:
            if a is not b:
                d = distance((a.x, a.y), (b.x, b.y))
                # Conservative static speed 20 km/h. Dynamic probe never slower.
                m.add_edge(a, b, distance=d, duration=math.ceil(d * 60 / 20000))
    t0 = time.perf_counter()
    result = m.solve(stop=MultipleCriteria([MaxIterations(10000), NoImprovement(2000)]),
                     seed=seed, display=False)
    elapsed = time.perf_counter() - t0
    if not result.best.is_feasible():
        return {"status": "NO_FEASIBLE_SOLUTION_FOUND", "routes": [],
                "runtime_s": elapsed, "iterations": result.num_iterations}
    routes = [{"jobs": [jobs[a.idx]["job_id"] for a in r if a.is_client()],
               "departure_min": r.start_time(), "reported_distance_m": r.distance()}
              for r in result.best.routes()]
    return {"status": "FEASIBLE", "routes": routes, "runtime_s": elapsed,
            "iterations": result.num_iterations, "objective_distance_m": result.best.distance()}


def travel_minutes(d, depart, dynamic):
    if not dynamic:
        return math.ceil(d * 60 / 20000)
    # Integration over clock minutes is FIFO, unlike selecting one travel-time
    # matrix from the initial departure and using it for the entire route.
    remain, elapsed = float(d), 0
    while remain > 1e-8:
        clock = depart + elapsed
        speed = 20000 if 420 <= clock < 540 or 960 <= clock < 1080 else 40000
        remain -= speed / 60
        elapsed += 1
    return elapsed


def simulate_route(case, route, by_id, dynamic=False):
    t = route["departure_min"]
    prev = case["depot_coord_m"]
    drive = wait = dist = 0
    visits = []
    violations = []
    if t < case["shift_start"]:
        violations.append("departure_before_shift")
    if sum(by_id[j]["weight_kg"] for j in route["jobs"]) > case["capacity_kg"]:
        violations.append("capacity")
    for jid in route["jobs"]:
        j = by_id[jid]
        if route["departure_min"] < j["release_min"]:
            violations.append(f"release:{jid}")
        d = distance(prev, j["coord_m"])
        travel = travel_minutes(d, t, dynamic)
        arrival = t + travel
        start = max(arrival, j["slot_start"], j["site_ready_min"])
        finish = start + j["service_min"]
        if finish > j["slot_end"]:
            violations.append(f"late:{jid}")
        if not j["site_ready"] or not j["production_ready"]:
            violations.append(f"readiness:{jid}")
        visits.append({"job_id": jid, "site": j["site"], "sequence": j["sequence"],
                       "arrival_min": arrival, "start_min": start, "end_min": finish})
        drive += travel
        wait += start - arrival
        dist += d
        t, prev = finish, j["coord_m"]
    d = distance(prev, case["depot_coord_m"])
    travel = travel_minutes(d, t, dynamic)
    dist += d
    drive += travel
    t += travel
    if t > case["shift_end"]:
        violations.append("return_after_shift")
    return {**route, "visits": visits, "distance_m": dist, "travel_min": drive,
            "waiting_min": wait, "return_min": t, "violations": violations}


def validate_plan(case, jobs, routes, dynamic=False):
    by_id = {j["job_id"]: j for j in jobs}
    seen = [jid for r in routes for jid in r["jobs"]]
    violations = []
    if sorted(seen) != sorted(by_id):
        violations.append("missing_duplicate_or_unknown_job")
    if len(routes) > case["fleet_size"]:
        violations.append("fleet")
    if any(jid not in by_id for jid in seen):
        return {"valid": False, "violations": violations, "routes": []}
    evaluated = [simulate_route(case, r, by_id, dynamic) for r in routes]
    for r in evaluated:
        violations.extend(r["violations"])
        if "reported_distance_m" in r and r["reported_distance_m"] != r["distance_m"]:
            violations.append("reported_distance_mismatch")
    visits = [v for r in evaluated for v in r["visits"]]
    for site in {j["site"] for j in jobs}:
        vs = sorted([v for v in visits if v["site"] == site], key=lambda v: v["sequence"])
        for a, b in zip(vs, vs[1:]):
            if a["end_min"] > b["start_min"]:
                violations.append(f"sequence_or_crane_overlap:{a['job_id']}:{b['job_id']}")
    return {"valid": not violations, "violations": violations, "routes": evaluated,
            "distance_m": sum(r["distance_m"] for r in evaluated),
            "travel_min": sum(r["travel_min"] for r in evaluated),
            "waiting_min": sum(r["waiting_min"] for r in evaluated),
            "vehicles": len(routes), "jobs_served": len(seen)}


def choose_departures(case, jobs, routes):
    by_id = {j["job_id"]: j for j in jobs}
    selected = []
    for r in routes:
        lower = max(case["shift_start"], *(by_id[j]["release_min"] for j in r["jobs"]))
        first = by_id[r["jobs"][0]]
        upper = first["slot_end"] - first["service_min"]
        options = []
        for depart in range(lower, upper + 1):
            trial = {**r, "departure_min": depart}
            s = simulate_route(case, trial, by_id, dynamic=True)
            if not s["violations"]:
                # Single operational objective: route duty excluding fixed service.
                # Later departure only breaks exact ties. No carbon claim here.
                key = (s["travel_min"] + s["waiting_min"], -depart)
                options.append((key, trial))
        if not options:
            return None
        selected.append(min(options, key=lambda x: x[0])[1])
    return selected


def fingerprint(routes):
    canonical = sorted((tuple(r["jobs"]), r["departure_min"]) for r in routes)
    return hashlib.sha256(repr(canonical).encode()).hexdigest()[:12]


def run():
    data_dir, result_dir = HERE / "data", HERE / "results"
    data_dir.mkdir(exist_ok=True)
    result_dir.mkdir(exist_ok=True)
    cfg = freeze.load_config()
    fid_before = freeze.freeze_id()
    case = generate_case()
    dump(data_dir / "synthetic_case.json", case)
    write_csv(data_dir / "components.csv", case["components"])
    write_csv(data_dir / "delivery_batches.csv", case["jobs"])
    jobs, deferred = eligibility(case)
    inst = vrp_projection(case, jobs, data_dir / "capacity_projection.vrp")
    base = solve_cvrp(inst, case["fleet_size"], cfg, diagnose_fleet=False)
    base_valid = validate_solution(inst, base).overall_pass
    base_routes = [{"jobs": [jobs[n - 2]["job_id"] for n in r.node_ids[1:-1]],
                    "departure_min": case["shift_start"], "reported_distance_m": r.distance}
                   for r in base.routes]
    base_operation = validate_plan(case, jobs, base_routes)
    dump(result_dir / "capacity_baseline.json", {"core_feasible": base_valid,
         "core_distance_m": base.total_distance, "core_runtime_s": base.runtime_s,
         "operational_evaluation": base_operation})

    seed_results, plans = [], {}
    for seed in (1, 2, 3):
        plan = solve_slots(case, jobs, seed)
        check = validate_plan(case, jobs, plan["routes"])
        plans[seed] = plan
        seed_results.append({"seed": seed, "status": plan["status"], "independent_valid": check["valid"],
                             "distance_m": check["distance_m"], "vehicles": check["vehicles"],
                             "runtime_s": round(plan.get("runtime_s", 0), 4),
                             "iterations": plan.get("iterations", 0), "fingerprint": fingerprint(plan["routes"])})
        dump(result_dir / f"fixed_slots_seed{seed}.json", {"solver": plan, "validation": check})
    write_csv(result_dir / "seed_results.csv", seed_results)
    repeated = solve_slots(case, jobs, 1)
    same = fingerprint(repeated["routes"]) == fingerprint(plans[1]["routes"])
    selected = choose_departures(case, jobs, plans[1]["routes"])
    green = validate_plan(case, jobs, selected or [], dynamic=True)
    static_departure = validate_plan(case, jobs, plans[1]["routes"], dynamic=True)
    early = validate_plan(case, jobs, [{**r, "departure_min": case["shift_start"]}
                                     for r in plans[1]["routes"]], dynamic=True)
    dump(result_dir / "departure_probe.json", {"traffic_model": "assumed FIFO 20/40 km/h",
         "same_routes_depart_0700": early, "enumerated_departures": green,
         "same_routes_static_solver_departures": static_departure,
         "carbon_saving": None, "note": "departure-only comparison on the SAME routes, jobs and fleet"})

    delayed = copy.deepcopy(case)
    next(j for j in delayed["jobs"] if j["job_id"] == "S2-B2")["site_ready"] = False
    remaining, excluded = eligibility(delayed)
    delayed_plan = solve_slots(delayed, remaining, 1)
    delayed_check = validate_plan(delayed, remaining, delayed_plan["routes"])
    dump(result_dir / "readiness_probe.json", {"deferred": excluded, "eligible_jobs": len(remaining),
         "served_components": sum(len(j["component_ids"]) for j in remaining),
         "solver": delayed_plan, "validation": delayed_check})

    checks = []
    def test(name, passed, detail):
        checks.append({"name": name, "pass": bool(passed), "detail": detail})
    test("36_components_two_families", len(case["components"]) == 36 and len(case["families"]) == 2, "12 batches, 4 sites")
    test("frozen_core_capacity_projection", base_valid, base.total_distance)
    test("fixed_slots_three_seeds", all(r["independent_valid"] for r in seed_results), seed_results)
    test("same_seed_repeated", same, fingerprint(repeated["routes"]))
    test("departure_probe_feasible", green["valid"] and early["valid"], "same routes, FIFO travel per leg")
    test("departure_objective_nonworsening", green["valid"] and
         green["travel_min"] + green["waiting_min"] <= early["travel_min"] + early["waiting_min"], "duty time excluding service")
    test("departure_vs_static_schedule", static_departure["valid"] and green["valid"] and
         green["travel_min"] + green["waiting_min"] <= static_departure["travel_min"] + static_departure["waiting_min"],
         "comparison against existing solver departures, not only all-at-07:00")
    test("readiness_cascade", len(excluded) == 2 and delayed_check["valid"], excluded)
    released = copy.deepcopy(case)
    next(j for j in released["jobs"] if j["job_id"] == "S1-B3")["release_min"] = 600
    release_plan = solve_slots(released, released["jobs"], 1)
    release_check = validate_plan(released, released["jobs"], release_plan["routes"])
    test("later_production_release", release_check["valid"], "S1-B3 cannot leave the plant before 10:00")
    dump(result_dir / "release_probe.json", {"solver": release_plan, "validation": release_check})
    for name, mutation, expected in [
        ("overweight_batch", lambda c: c["jobs"][0].update(weight_kg=9001), "PROVEN_INFEASIBLE_BATCH_CAPACITY"),
        ("insufficient_fleet", lambda c: c.update(fleet_size=1), "PROVEN_INFEASIBLE_FLEET_CAPACITY_SINGLE_TRIP"),
        ("slot_shorter_than_service", lambda c: c["jobs"][0].update(slot_end=550), "PROVEN_INFEASIBLE_SERVICE_SLOT"),
        ("overlapping_slots", lambda c: c["jobs"][1].update(slot_start=550), "UNSUPPORTED_OVERLAPPING_SEQUENCE_SLOTS"),
        ("unapproved_loading", lambda c: c["jobs"][0].update(load_plan_approved_assumption=False), "INPUT_REQUIRES_LOAD_PLAN")]:
        changed = copy.deepcopy(case)
        mutation(changed)
        observed = precheck(changed, changed["jobs"])
        test(name, observed == expected, observed)
    missing = copy.deepcopy(plans[1]["routes"])
    missing[0]["jobs"].pop()
    test("validator_rejects_missing_job", not validate_plan(case, jobs, missing)["valid"], "mutated plan")
    duplicate = copy.deepcopy(plans[1]["routes"])
    duplicate[0]["jobs"].append(duplicate[0]["jobs"][0])
    test("validator_rejects_duplicate_job", not validate_plan(case, jobs, duplicate)["valid"], "mutated plan")
    late = copy.deepcopy(plans[1]["routes"])
    late[0]["departure_min"] = 1000
    test("validator_rejects_late_plan", not validate_plan(case, jobs, late)["valid"], "mutated plan")
    # Two routes to the same crane, both inside deliberately overlapping windows.
    # Capacity/TW checks alone pass; global precedence/resource check must fail.
    crane_case = copy.deepcopy(case)
    crane_jobs = copy.deepcopy(jobs[:2])
    for j in crane_jobs:
        j.update(slot_start=540, slot_end=640)
    crane_routes = [{"jobs": [j["job_id"]], "departure_min": 420} for j in crane_jobs]
    crane_check = validate_plan(crane_case, crane_jobs, crane_routes)
    test("validator_rejects_cross_route_crane_overlap", any("crane_overlap" in v for v in crane_check["violations"]), crane_check["violations"])
    # FIFO: later departures cannot arrive earlier, including the peak boundary.
    arrivals = [t + travel_minutes(30000, t, True) for t in range(480, 571)]
    test("traffic_model_fifo_boundary", all(a <= b for a, b in zip(arrivals, arrivals[1:])), "30 km at 08:00-09:30")
    uncertain = copy.deepcopy(case)
    uncertain["shift_end"] = 500
    unfound = solve_slots(uncertain, uncertain["jobs"], 1)
    test("solver_failure_not_proof", unfound["status"] == "NO_FEASIBLE_SOLUTION_FOUND",
         unfound["status"])
    fid_after = freeze.freeze_id()
    test("core_unchanged", fid_before == fid_after, {"before": fid_before, "after": fid_after})
    write_csv(result_dir / "gate_checks.csv", checks)
    source = inspect.getsource(importlib.import_module("pyvrp.solve").solve)
    (HERE / "evidence" / "installed_pyvrp_solve.txt").write_text(source, encoding="utf-8")
    decision_path = HERE / "decision.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8")) if decision_path.exists() else {}
    summary = {"technical_probe_pass": all(c["pass"] for c in checks),
               "topic_decision": decision.get("status", "PENDING_USER_CONFIRMATION"),
               "topic_decision_source": "decision.json" if decision_path.exists() else None,
               "core_freeze_id": fid_after,
               "pyvrp_version": freeze.engine_version(), "engine_observed": "IteratedLocalSearch",
               "python": platform.python_version(), "platform": platform.platform(),
               "dataset_sha256": hashlib.sha256((data_dir / "synthetic_case.json").read_bytes()).hexdigest(),
               "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "core_projection_feasible": base_valid, "capacity_baseline_operational_valid": base_operation["valid"],
               "seed_results": seed_results, "same_seed_repeat": same,
               "departure_probe": {"distance_m": green["distance_m"], "vehicles": green["vehicles"],
                  "early_travel_min": early["travel_min"], "selected_travel_min": green["travel_min"],
                  "early_wait_min": early["waiting_min"], "selected_wait_min": green["waiting_min"],
                  "static_schedule_travel_min": static_departure["travel_min"],
                  "static_schedule_wait_min": static_departure["waiting_min"]},
               "readiness": {"eligible_jobs": len(remaining), "deferred_jobs": len(excluded), "valid": delayed_check["valid"]},
               "checks": checks}
    dump(result_dir / "gate_summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "checks"}, indent=2))
    print(f"CHECKS: {sum(c['pass'] for c in checks)}/{len(checks)}")
    return 0 if summary["technical_probe_pass"] else 1


if __name__ == "__main__":
    sys.exit(run())
