"""Independent plan validator and JSON CLI. Does not call an optimizer."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from contract import OUTPUT_SCHEMA, check_shape, input_hash, issue, prepare_case, read_json, travel_minutes


def validate_plan(case, plan):
    prepared = prepare_case(case)
    errors = check_shape(plan, OUTPUT_SCHEMA)
    result = {"valid": False, "feasible_for_eligible_work": False,
              "all_requested_served": False, "issues": errors, "recomputed_metrics": None}
    if prepared["status"] not in ("READY", "NO_ELIGIBLE_WORK"):
        errors.append(issue("CASE_NOT_READY", "$", prepared["status"]))
        return result
    if errors:
        return result
    if plan["case_id"] != case["case_id"] or plan["input_sha256"] != input_hash(case):
        errors.append(issue("INPUT_IDENTITY", "$", "Plan must reference this exact input revision"))
    eligible = {b["batch_id"]: b for b in prepared["eligible_batches"]}
    deferred = [b["batch_id"] for b in prepared["deferred_batches"]]
    stops = [s for r in plan["routes"] for s in r["stops"]]
    visited = [s["batch_id"] for s in stops]
    if Counter(plan["deferred_batch_ids"]) != Counter(deferred):
        errors.append(issue("DEFERRED_COVERAGE", "deferred_batch_ids", "Must report every deferred batch exactly once"))
    if Counter(plan["served_batch_ids"]) != Counter(visited):
        errors.append(issue("SERVED_COVERAGE", "served_batch_ids", "Served list must match route visits"))
    if plan["status"] == "NO_FEASIBLE_SOLUTION_FOUND":
        if prepared["status"] != "READY" or plan["routes"] or plan["served_batch_ids"] or plan["metrics"] is not None:
            errors.append(issue("FAILURE_ENVELOPE", "$", "Search failure has no routes, served work or feasible metrics"))
        if Counter(plan["unserved_eligible_batch_ids"]) != Counter(eligible.keys()):
            errors.append(issue("UNSERVED_COVERAGE", "unserved_eligible_batch_ids", "All eligible work remains unserved"))
        result["valid"] = not errors
        return result  # A valid failure report is not a feasible solution.
    expected_status = "FEASIBLE" if eligible else "NO_ELIGIBLE_WORK"
    if plan["status"] != expected_status:
        errors.append(issue("PLAN_STATUS", "status", f"Expected {expected_status}"))
    if plan["unserved_eligible_batch_ids"]:
        errors.append(issue("UNSERVED_ELIGIBLE_WORK", "unserved_eligible_batch_ids", "Success must serve all eligible work"))
    if Counter(visited) != Counter(eligible.keys()):
        errors.append(issue("BATCH_COVERAGE", "routes", "Eligible batches must be visited exactly once; deferred work must not be visited"))
    if any(bid not in eligible for bid in visited):
        return result
    fleet = case["fleet"]
    vehicle_ids = [r["vehicle_id"] for r in plan["routes"]]
    if len(vehicle_ids) != len(set(vehicle_ids)) or not set(vehicle_ids).issubset(fleet["vehicle_ids"]):
        errors.append(issue("VEHICLE_ASSIGNMENT", "routes", "Use an available physical vehicle once at most"))
    sites = {s["site_id"]: s for s in case["sites"]}
    locations = {loc: i for i, loc in enumerate(case["travel"]["location_ids"])}
    matrix = case["travel"]["distance_m"]
    depot = case["depot"]["location_id"]
    total_distance = total_drive = total_wait = 0
    site_visits = {sid: [] for sid in sites}
    for route in plan["routes"]:
        vid = route["vehicle_id"]
        clock, loc = route["departure_min"], depot
        route_distance = 0
        demand = sum(eligible[s["batch_id"]]["demand_kg"] for s in route["stops"])
        if demand > fleet["capacity_kg"]:
            errors.append(issue("CAPACITY", vid, f"{demand} kg exceeds {fleet['capacity_kg']} kg"))
        if clock < fleet["shift_start_min"]:
            errors.append(issue("SHIFT_START", vid, "Departure is before shift"))
        if any(clock < eligible[s["batch_id"]]["release_min"] for s in route["stops"]):
            errors.append(issue("PRODUCTION_RELEASE", vid, "All loaded components must be released before departure"))
        for stop in route["stops"]:
            bid = stop["batch_id"]
            batch = eligible[bid]
            destination = sites[batch["site_id"]]["location_id"]
            duration = travel_minutes(case, loc, destination, clock)
            if duration is None:
                errors.append(issue("TRAVEL_OUTSIDE_DAY", bid, "Traffic profile ends before arrival"))
                duration = 0
            if stop["arrival_min"] != clock + duration:
                errors.append(issue("ARRIVAL_TIME", bid, "Arrival disagrees with previous service end and travel model"))
            if stop["start_min"] < stop["arrival_min"]:
                errors.append(issue("SERVICE_BEFORE_ARRIVAL", bid, "Service cannot begin before arrival"))
            if stop["end_min"] != stop["start_min"] + batch["service_min"]:
                errors.append(issue("SERVICE_DURATION", bid, "End must equal start plus declared service duration"))
            if stop["start_min"] < batch["tw_early_min"] or stop["end_min"] > batch["slot_end_min"]:
                errors.append(issue("CRANE_SLOT", bid, "Whole service must fit crane slot and site-ready time"))
            route_distance += matrix[locations[loc]][locations[destination]]
            total_drive += duration
            total_wait += max(0, stop["start_min"] - stop["arrival_min"])
            site_visits[batch["site_id"]].append({**stop, "sequence": batch["sequence"]})
            clock, loc = stop["end_min"], destination
        duration = travel_minutes(case, loc, depot, clock)
        if duration is None:
            errors.append(issue("TRAVEL_OUTSIDE_DAY", vid, "Traffic profile ends before depot return"))
            duration = 0
        route_distance += matrix[locations[loc]][locations[depot]]
        total_drive += duration
        if route["return_min"] != clock + duration:
            errors.append(issue("RETURN_TIME", vid, "Return must include final leg to depot"))
        if clock + duration > fleet["shift_end_min"] or route["return_min"] > fleet["shift_end_min"]:
            errors.append(issue("SHIFT_END", vid, "Vehicle returns after shift"))
        if route["distance_m"] != route_distance:
            errors.append(issue("ROUTE_DISTANCE", vid, f"Expected {route_distance} m"))
        total_distance += route_distance
    for sid, visits in site_visits.items():
        by_rank = sorted(visits, key=lambda s: s["sequence"])
        for a, b in zip(by_rank, by_rank[1:]):
            if a["end_min"] > b["start_min"]:
                errors.append(issue("INSTALLATION_SEQUENCE", sid, f"{a['batch_id']} must finish before {b['batch_id']}"))
        by_time = sorted(visits, key=lambda s: s["start_min"])
        for a, b in zip(by_time, by_time[1:]):
            if a["end_min"] > b["start_min"]:
                errors.append(issue("CRANE_OVERLAP", sid, f"{a['batch_id']} and {b['batch_id']} overlap across the fleet"))
    metrics = {"distance_m": total_distance, "travel_min": total_drive, "waiting_min": total_wait,
               "vehicles_used": len(plan["routes"]),
               "served_components": sum(len(eligible[bid]["component_ids"]) for bid in visited),
               "deferred_components": prepared["counts"]["deferred_components"]}
    if plan["metrics"] != metrics:
        errors.append(issue("METRICS_MISMATCH", "metrics", "Reported metrics must equal independent recomputation"))
    result.update(valid=not errors, feasible_for_eligible_work=not errors,
                  all_requested_served=not errors and not deferred, recomputed_metrics=metrics)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("--plan", type=Path)
    args = parser.parse_args()
    try:
        case = read_json(args.case)
        if args.plan:
            plan = read_json(args.plan)
            report = validate_plan(case, plan)
            ok = report["valid"]
        else:
            report = prepare_case(case)
            ok = report["status"] in ("READY", "NO_ELIGIBLE_WORK")
    except (OSError, UnicodeError, ValueError) as exc:
        report = {"status": "INVALID_INPUT", "issues": [issue("READ_ERROR", "$", str(exc))]}
        ok = False
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
