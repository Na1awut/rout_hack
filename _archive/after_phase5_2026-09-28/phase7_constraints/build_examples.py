"""Adapt saved Phase 6 evidence to the Phase 7 contract, without solving again."""
import copy
import hashlib
import json
import math
from pathlib import Path

from contract import INPUT_SCHEMA, OUTPUT_SCHEMA, VERSION, input_hash, prepare_case

HERE = Path(__file__).resolve().parent
PHASE6 = HERE.parent / "phase6_topic_selection"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def convert_case(legacy):
    coords = {"DEPOT": legacy["depot_coord_m"]}
    for job in legacy["jobs"]:
        sid = job["site"]
        if sid in coords and coords[sid] != job["coord_m"]:
            raise ValueError(f"Inconsistent coordinates for {sid}")
        coords[sid] = job["coord_m"]
        parts = [c for c in legacy["components"] if c["component_id"] in job["component_ids"]]
        if len(parts) != len(job["component_ids"]) or sum(c["weight_kg"] for c in parts) != job["weight_kg"]:
            raise ValueError(f"Inconsistent legacy batch mass or component references: {job['job_id']}")
    order = list(coords)
    d = [[math.floor(math.hypot(coords[a][0] - coords[b][0], coords[a][1] - coords[b][1]) + .5)
          for b in order] for a in order]
    return {"schema_version": VERSION, "case_id": "PrecastFlow-P6-normal-v1", "data_kind": "synthetic",
            "units": {"mass": "kg", "distance": "m", "time": "minute_after_midnight"},
            "sources": [{"source_id": "P6-SIM", "kind": "assumption",
                         "reference": "phase6_topic_selection/data/synthetic_case.json; operational data are simulated"}],
            "depot": {"location_id": "DEPOT"},
            "sites": [{"site_id": sid, "location_id": sid, "crane_id": f"CRANE-{sid}"} for sid in order[1:]],
            "fleet": {"vehicle_ids": [f"V{i + 1:02d}" for i in range(legacy["fleet_size"])],
                      "capacity_kg": legacy["capacity_kg"], "shift_start_min": legacy["shift_start"],
                      "shift_end_min": legacy["shift_end"], "source_id": "P6-SIM"},
            "components": [{"component_id": c["component_id"], "site_id": c["site"],
                            "weight_kg": c["weight_kg"], "installation_rank": c["installation_rank"],
                            "production_ready": True, "release_min": c["production_ready_min"],
                            "source_id": "P6-SIM"} for c in legacy["components"]],
            "batches": [{"batch_id": j["job_id"], "site_id": j["site"], "component_ids": j["component_ids"],
                         "sequence": j["sequence"], "service_min": j["service_min"],
                         "slot_start_min": j["slot_start"], "slot_end_min": j["slot_end"],
                         "site_ready": j["site_ready"], "site_ready_min": j["site_ready_min"],
                         "load_plan_approved": j["load_plan_approved_assumption"],
                         "source_id": "P6-SIM"} for j in legacy["jobs"]],
            "travel": {"location_ids": order, "distance_m": d,
                       "duration_upper_min": [[(n * 60 + 19999) // 20000 for n in row] for row in d],
                       "mode": "FIFO_SPEED_BANDS", "speed_bands": [
                           {"start_min": 0, "end_min": 420, "speed_kmh": 40},
                           {"start_min": 420, "end_min": 540, "speed_kmh": 20},
                           {"start_min": 540, "end_min": 960, "speed_kmh": 40},
                           {"start_min": 960, "end_min": 1080, "speed_kmh": 20},
                           {"start_min": 1080, "end_min": 1440, "speed_kmh": 40}],
                       "source_id": "P6-SIM"}}


def convert_plan(case, evaluated):
    prepared = prepare_case(case)
    if prepared["status"] != "READY":
        raise ValueError(prepared["issues"])
    routes = [{"vehicle_id": case["fleet"]["vehicle_ids"][i],
               "departure_min": r["departure_min"], "return_min": r["return_min"], "distance_m": r["distance_m"],
               "stops": [{"batch_id": s["job_id"], "arrival_min": s["arrival_min"],
                          "start_min": s["start_min"], "end_min": s["end_min"]} for s in r["visits"]]}
              for i, r in enumerate(evaluated["routes"])]
    return {"schema_version": VERSION, "case_id": case["case_id"], "input_sha256": input_hash(case),
            "status": "FEASIBLE", "served_batch_ids": [s["batch_id"] for r in routes for s in r["stops"]],
            "deferred_batch_ids": [b["batch_id"] for b in prepared["deferred_batches"]],
            "unserved_eligible_batch_ids": [], "routes": routes,
            "metrics": {"distance_m": evaluated["distance_m"], "travel_min": evaluated["travel_min"],
                        "waiting_min": evaluated["waiting_min"], "vehicles_used": evaluated["vehicles"],
                        "served_components": prepared["counts"]["eligible_components"],
                        "deferred_components": prepared["counts"]["deferred_components"]}}


def main():
    legacy_path = PHASE6 / "data/synthetic_case.json"
    legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    read = lambda name: json.loads((PHASE6 / "results" / name).read_text(encoding="utf-8"))
    normal = convert_case(legacy)
    plan = convert_plan(normal, read("departure_probe.json")["enumerated_departures"])
    static = copy.deepcopy(normal)
    static["case_id"] = "PrecastFlow-P6-static-v1"
    static["travel"].update(mode="STATIC_MATRIX", speed_bands=[])
    static_plan = convert_plan(static, read("fixed_slots_seed1.json")["validation"])
    delayed = copy.deepcopy(static)
    delayed["case_id"] = "PrecastFlow-P6-readiness-v1"
    next(b for b in delayed["batches"] if b["batch_id"] == "S2-B2")["site_ready"] = False
    delayed_plan = convert_plan(delayed, read("readiness_probe.json")["validation"])
    no_work = copy.deepcopy(normal)
    no_work["case_id"] = "PrecastFlow-no-eligible-v1"
    for c in no_work["components"]:
        c["production_ready"] = False
    empty_plan = {"schema_version": VERSION, "case_id": no_work["case_id"], "input_sha256": input_hash(no_work),
                  "status": "NO_ELIGIBLE_WORK", "served_batch_ids": [],
                  "deferred_batch_ids": [b["batch_id"] for b in no_work["batches"]],
                  "unserved_eligible_batch_ids": [], "routes": [],
                  "metrics": {"distance_m": 0, "travel_min": 0, "waiting_min": 0,
                              "vehicles_used": 0, "served_components": 0, "deferred_components": 36}}
    for name, case, output in (("normal", normal, plan), ("static", static, static_plan),
                              ("readiness", delayed, delayed_plan), ("no_work", no_work, empty_plan)):
        write(HERE / "examples" / f"{name}.input.json", case)
        write(HERE / "examples" / f"{name}.output.json", output)
        write(HERE / "examples" / f"{name}.prepared.json", prepare_case(case))
    for name, schema in (("case", INPUT_SCHEMA), ("plan", OUTPUT_SCHEMA)):
        write(HERE / "schemas" / f"{name}.schema.json", {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": f"PrecastFlow {name} contract {VERSION}", **schema})
    sources = [legacy_path] + [PHASE6 / "results" / n for n in (
        "departure_probe.json", "fixed_slots_seed1.json", "readiness_probe.json")]
    write(HERE / "examples" / "provenance.json", {
        "note": "Converted from saved Phase 6 evidence; no new solver runs. no_work is a contract edge case.",
        "sources": [{"path": p.relative_to(HERE.parent).as_posix(),
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources]})
    print("Created 4 input/output pairs, preparation reports, schemas and provenance.")


if __name__ == "__main__":
    main()
