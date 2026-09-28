"""PrecastFlow 1.0 input contract and deterministic constraint preparation.

No solver imports. JSON schemas use only the explicitly supported keywords in
check_shape(); this is a validator for these contracts, not a general-purpose
JSON Schema implementation. Unknown fields fail closed to expose typos.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

VERSION = "1.0"


def obj(properties, optional=()):
    return {"type": "object", "properties": properties,
            "required": [k for k in properties if k not in optional], "additionalProperties": False}


def arr(items, minimum=0):
    return {"type": "array", "items": items, "minItems": minimum}


def integer(minimum=0, maximum=None):
    spec = {"type": "integer", "minimum": minimum}
    if maximum is not None:
        spec["maximum"] = maximum
    return spec


def enum(*values):
    return {"type": "string", "enum": list(values)}


TEXT = {"type": "string", "minLength": 1}
BOOL = {"type": "boolean"}
MINUTE = integer(0, 1440)
UNITS = obj({"mass": {"const": "kg"}, "distance": {"const": "m"},
             "time": {"const": "minute_after_midnight"}})
INPUT_SCHEMA = obj({
    "schema_version": {"const": VERSION}, "case_id": TEXT,
    "data_kind": enum("synthetic", "mixed", "measured"), "units": UNITS,
    "sources": arr(obj({"source_id": TEXT, "kind": enum("assumption", "derived", "measured", "published"),
                        "reference": TEXT}), 1),
    "depot": obj({"location_id": TEXT}),
    "sites": arr(obj({"site_id": TEXT, "location_id": TEXT, "crane_id": TEXT})),
    "fleet": obj({"vehicle_ids": arr(TEXT), "capacity_kg": integer(1),
                  "shift_start_min": MINUTE, "shift_end_min": MINUTE,
                  "source_id": TEXT}),
    "components": arr(obj({"component_id": TEXT, "site_id": TEXT, "weight_kg": integer(1),
                           "installation_rank": integer(1), "production_ready": BOOL,
                           "release_min": MINUTE, "source_id": TEXT})),
    "batches": arr(obj({"batch_id": TEXT, "site_id": TEXT, "component_ids": arr(TEXT, 1),
                        "sequence": integer(1), "service_min": integer(1, 1440),
                        "slot_start_min": MINUTE, "slot_end_min": MINUTE,
                        "site_ready": BOOL, "site_ready_min": MINUTE,
                        "load_plan_approved": BOOL, "source_id": TEXT})),
    "travel": obj({"location_ids": arr(TEXT, 1), "distance_m": arr(arr(integer())),
                   "duration_upper_min": arr(arr(integer(0, 1440))),
                   "mode": enum("STATIC_MATRIX", "FIFO_SPEED_BANDS"),
                   "speed_bands": arr(obj({"start_min": MINUTE, "end_min": MINUTE,
                                           "speed_kmh": integer(1, 200)})),
                   "source_id": TEXT})
})
METRICS_SCHEMA = obj({name: integer() for name in (
    "distance_m", "travel_min", "waiting_min", "vehicles_used",
    "served_components", "deferred_components")})
OUTPUT_SCHEMA = obj({
    "schema_version": {"const": VERSION}, "case_id": TEXT, "input_sha256": TEXT,
    "status": enum("FEASIBLE", "NO_ELIGIBLE_WORK", "NO_FEASIBLE_SOLUTION_FOUND"),
    "served_batch_ids": arr(TEXT), "deferred_batch_ids": arr(TEXT),
    "unserved_eligible_batch_ids": arr(TEXT),
    "routes": arr(obj({"vehicle_id": TEXT, "departure_min": MINUTE, "return_min": MINUTE,
                       "distance_m": integer(),
                       "stops": arr(obj({"batch_id": TEXT, "arrival_min": MINUTE,
                                         "start_min": MINUTE, "end_min": MINUTE}), 1)})),
    "metrics": {**METRICS_SCHEMA, "type": ["object", "null"]}
})


def issue(code, path, detail):
    return {"code": code, "path": path, "detail": detail}


def check_shape(value, spec, path="$"):
    errors = []
    if "const" in spec and value != spec["const"]:
        return [issue("INVALID_VALUE", path, f"Expected {spec['const']!r}")]
    expected = spec.get("type")
    types = expected if isinstance(expected, list) else [expected] if expected else []
    matches = {"object": type(value) is dict, "array": type(value) is list,
               "integer": type(value) is int, "boolean": type(value) is bool,
               "string": type(value) is str, "null": value is None}
    if types and not any(matches[t] for t in types):
        return [issue("INVALID_TYPE", path, f"Expected {expected}; got {type(value).__name__}")]
    if value is None:
        return errors
    if "enum" in spec and value not in spec["enum"]:
        errors.append(issue("INVALID_VALUE", path, f"Expected one of {spec['enum']}"))
    if type(value) is int:
        if value < spec.get("minimum", value) or value > spec.get("maximum", value):
            errors.append(issue("OUT_OF_RANGE", path, "Numeric value outside contract range"))
    if type(value) is str and len(value.strip()) < spec.get("minLength", 0):
        errors.append(issue("EMPTY_TEXT", path, "Nonblank text required"))
    if type(value) is dict:
        properties = spec.get("properties", {})
        for key in spec.get("required", []):
            if key not in value:
                errors.append(issue("MISSING_FIELD", f"{path}.{key}", "Required field"))
        for key in value:
            if key not in properties:
                errors.append(issue("UNKNOWN_FIELD", f"{path}.{key}", "Field not supported by this contract"))
            else:
                errors.extend(check_shape(value[key], properties[key], f"{path}.{key}"))
    if type(value) is list:
        if len(value) < spec.get("minItems", 0):
            errors.append(issue("EMPTY_LIST", path, "Too few entries"))
        for index, item in enumerate(value):
            errors.extend(check_shape(item, spec["items"], f"{path}[{index}]"))
    return errors


def input_hash(case):
    payload = json.dumps(case, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"Non-finite JSON value: {value}")

    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def prepare_case(case):
    """Validate, derive batch demand/release, partition readiness, then precheck.

    READY means eligible for a solver attempt, not a feasible-plan guarantee.
    Proven failures have simple witnesses; unsupported scope is kept separate.
    """
    report = {"schema_version": VERSION, "status": "INVALID_INPUT", "issues": [],
              "eligible_batches": [], "deferred_batches": [], "counts": {}}
    errors = check_shape(case, INPUT_SCHEMA)
    report["issues"] = errors
    if errors:
        return report
    report.update(case_id=case["case_id"], input_sha256=input_hash(case))
    unsupported = []

    def unique(values, path):
        if len(values) != len(set(values)):
            errors.append(issue("DUPLICATE_ID", path, "IDs must be unique"))

    for field, key in (("sites", "site_id"), ("components", "component_id"),
                       ("batches", "batch_id"), ("sources", "source_id")):
        unique([x[key] for x in case[field]], field)
    unique(case["fleet"]["vehicle_ids"], "fleet.vehicle_ids")
    travel = case["travel"]
    locations = travel["location_ids"]
    unique(locations, "travel.location_ids")
    if errors:
        return report
    source_ids = {s["source_id"] for s in case["sources"]}
    if case["data_kind"] == "measured" and any(s["kind"] == "assumption" for s in case["sources"]):
        errors.append(issue("PROVENANCE_CONFLICT", "data_kind", "Assumption sources require synthetic or mixed labeling"))
    sites = {s["site_id"]: s for s in case["sites"]}
    components = {c["component_id"]: c for c in case["components"]}
    for kind in ("components", "batches"):
        for x in case[kind]:
            if x["site_id"] not in sites:
                errors.append(issue("UNKNOWN_SITE", kind, x["site_id"]))
    for path, x in [("fleet", case["fleet"]), ("travel", travel)] + [
            (kind, item) for kind in ("components", "batches") for item in case[kind]]:
        if x["source_id"] not in source_ids:
            errors.append(issue("UNKNOWN_SOURCE", path, x["source_id"]))
    expected_locations = {case["depot"]["location_id"]} | {s["location_id"] for s in sites.values()}
    if set(locations) != expected_locations:
        errors.append(issue("LOCATION_MAPPING", "travel.location_ids", "Must equal depot/site locations"))
    if len({s["crane_id"] for s in sites.values()}) != len(sites):
        unsupported.append(issue("SHARED_CRANE", "sites", "One independent crane per site in v1"))
    fleet = case["fleet"]
    if fleet["shift_start_min"] >= fleet["shift_end_min"]:
        errors.append(issue("INVALID_SHIFT", "fleet", "Shift must start before it ends within one day"))
    for key in ("distance_m", "duration_upper_min"):
        matrix = travel[key]
        if len(matrix) != len(locations) or any(len(row) != len(locations) for row in matrix):
            errors.append(issue("MATRIX_SHAPE", f"travel.{key}", "Expected square matrix in location_ids order"))
        elif any(matrix[i][i] != 0 for i in range(len(locations))):
            errors.append(issue("MATRIX_DIAGONAL", f"travel.{key}", "Diagonal must be zero"))
    bands = travel["speed_bands"]
    if travel["mode"] == "STATIC_MATRIX" and bands:
        errors.append(issue("UNUSED_SPEED_BANDS", "travel.speed_bands", "Static mode requires an empty list"))
    if travel["mode"] == "FIFO_SPEED_BANDS":
        if (not bands or bands[0]["start_min"] != 0 or bands[-1]["end_min"] != 1440
                or any(b["start_min"] >= b["end_min"] for b in bands)
                or any(a["end_min"] != b["start_min"] for a, b in zip(bands, bands[1:]))):
            errors.append(issue("SPEED_BAND_COVERAGE", "travel.speed_bands", "Ordered nonoverlapping bands must cover [0,1440)"))
        elif not errors:
            slowest = min(b["speed_kmh"] for b in bands) * 1000
            for i, row in enumerate(travel["distance_m"]):
                for j, distance_m in enumerate(row):
                    conservative = (distance_m * 60 + slowest - 1) // slowest
                    if travel["duration_upper_min"][i][j] < conservative:
                        errors.append(issue("NONCONSERVATIVE_DURATION", f"travel.duration_upper_min[{i}][{j}]",
                                            f"Must be at least {conservative} minutes for this speed model"))
    assigned = []
    for batch in case["batches"]:
        bid = batch["batch_id"]
        assigned.extend(batch["component_ids"])
        if batch["slot_start_min"] >= batch["slot_end_min"]:
            errors.append(issue("INVALID_SLOT", bid, "Slot start must precede slot end"))
        for cid in batch["component_ids"]:
            if cid not in components:
                errors.append(issue("UNKNOWN_COMPONENT", bid, cid))
            elif components[cid]["site_id"] != batch["site_id"]:
                errors.append(issue("COMPONENT_SITE_MISMATCH", bid, cid))
    if Counter(assigned) != Counter(components.keys()):
        errors.append(issue("COMPONENT_COVERAGE", "batches", "Every requested component must occur in exactly one batch"))
    if errors:
        return report
    for sid in sites:
        batches = sorted((b for b in case["batches"] if b["site_id"] == sid), key=lambda b: b["sequence"])
        if [b["sequence"] for b in batches] != list(range(1, len(batches) + 1)):
            errors.append(issue("BATCH_SEQUENCE", sid, "Sequence within planning horizon must be 1..N without gaps"))
        ranks = [components[c]["installation_rank"] for b in batches for c in b["component_ids"]]
        if ranks != list(range(1, len(ranks) + 1)):
            errors.append(issue("COMPONENT_SEQUENCE", sid, "Ordered batches must partition consecutive installation ranks 1..N"))
        for a, b in zip(batches, batches[1:]):
            if a["slot_end_min"] > b["slot_start_min"]:
                unsupported.append(issue("OVERLAPPING_SEQUENCE_SLOTS", sid,
                                         f"{a['batch_id']} / {b['batch_id']}: fixed sequence requires separated slots"))
    if errors:
        return report
    if unsupported:
        report.update(status="UNSUPPORTED_INPUT", issues=unsupported)
        return report

    for sid in sorted(sites):
        blocked_by = None
        for b in sorted((b for b in case["batches"] if b["site_id"] == sid), key=lambda b: b["sequence"]):
            parts = [components[c] for c in b["component_ids"]]
            reasons = []
            if not all(c["production_ready"] for c in parts):
                reasons.append("PRODUCTION_NOT_READY")
            if not b["site_ready"]:
                reasons.append("SITE_NOT_READY")
            if blocked_by:
                reasons.append("PREDECESSOR_DEFERRED")
            if reasons:
                blocked_by = blocked_by or b["batch_id"]
                report["deferred_batches"].append({"batch_id": b["batch_id"], "component_ids": b["component_ids"],
                    "reason_codes": reasons, "blocked_by_batch_id": blocked_by})
            else:
                report["eligible_batches"].append({**b, "demand_kg": sum(c["weight_kg"] for c in parts),
                    "release_min": max(c["release_min"] for c in parts),
                    "tw_early_min": max(b["slot_start_min"], b["site_ready_min"]),
                    "tw_late_min": b["slot_end_min"] - b["service_min"]})
    eligible = report["eligible_batches"]
    report["counts"] = {"requested_batches": len(case["batches"]), "requested_components": len(components),
                        "eligible_batches": len(eligible), "eligible_components": sum(len(b["component_ids"]) for b in eligible),
                        "deferred_batches": len(report["deferred_batches"]),
                        "deferred_components": sum(len(b["component_ids"]) for b in report["deferred_batches"]),
                        "eligible_demand_kg": sum(b["demand_kg"] for b in eligible)}
    unsupported = [issue("LOAD_PLAN_REQUIRED", b["batch_id"], "Eligible batch requires approved loading assumption")
                   for b in eligible if not b["load_plan_approved"]]
    if unsupported:
        report.update(status="UNSUPPORTED_INPUT", issues=unsupported)
        return report
    proofs = []
    for b in eligible:
        if b["demand_kg"] > fleet["capacity_kg"]:
            proofs.append(issue("BATCH_CAPACITY", b["batch_id"], f"{b['demand_kg']} kg > {fleet['capacity_kg']} kg"))
        earliest = max(b["tw_early_min"], b["release_min"], fleet["shift_start_min"])
        latest_finish = min(b["slot_end_min"], fleet["shift_end_min"])
        if earliest + b["service_min"] > latest_finish:
            proofs.append(issue("IMPOSSIBLE_TIME_INTERVAL", b["batch_id"], "Service cannot fit even with zero travel time"))
    total = report["counts"]["eligible_demand_kg"]
    if total > fleet["capacity_kg"] * len(fleet["vehicle_ids"]):
        proofs.append(issue("FLEET_CAPACITY", "fleet", f"{total} kg exceeds single-trip fleet capacity"))
    report.update(status="PROVEN_INFEASIBLE" if proofs else "READY" if eligible else "NO_ELIGIBLE_WORK", issues=proofs)
    return report


def travel_minutes(case, origin, destination, departure_min):
    """Returns None if a dynamic traversal leaves the specified day.

    Integer minute integration avoids floating point drift. Static matrices may
    be asymmetric. FIFO bands have a shared positive speed for the entire fleet.
    """
    travel = case["travel"]
    i, j = travel["location_ids"].index(origin), travel["location_ids"].index(destination)
    if travel["mode"] == "STATIC_MATRIX":
        return travel["duration_upper_min"][i][j]
    remaining = travel["distance_m"][i][j] * 60
    elapsed = 0
    while remaining > 0:
        clock = departure_min + elapsed
        if clock >= 1440:
            return None
        band = next(b for b in travel["speed_bands"] if b["start_min"] <= clock < b["end_min"])
        remaining -= band["speed_kmh"] * 1000
        elapsed += 1
    return elapsed
