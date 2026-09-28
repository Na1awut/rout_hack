"""Hand-derived oracles, saved-evidence integration and adversarial mutations."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from contract import input_hash, prepare_case, read_json, travel_minutes
from validate_contract import validate_plan

HERE = Path(__file__).resolve().parent


def hand_case():
    return {"schema_version": "1.0", "case_id": "hand-two-batches", "data_kind": "synthetic",
            "units": {"mass": "kg", "distance": "m", "time": "minute_after_midnight"},
            "sources": [{"source_id": "HAND", "kind": "assumption", "reference": "Hand-derived fixture"}],
            "depot": {"location_id": "D"},
            "sites": [{"site_id": "S", "location_id": "L", "crane_id": "CRANE"}],
            "fleet": {"vehicle_ids": ["V1", "V2"], "capacity_kg": 3000,
                      "shift_start_min": 420, "shift_end_min": 1020, "source_id": "HAND"},
            "components": [{"component_id": f"C{i}", "site_id": "S", "weight_kg": 1000,
                            "installation_rank": i, "production_ready": True, "release_min": 420,
                            "source_id": "HAND"} for i in (1, 2)],
            "batches": [{"batch_id": f"B{i}", "site_id": "S", "component_ids": [f"C{i}"],
                         "sequence": i, "service_min": 20, "slot_start_min": start,
                         "slot_end_min": start + 30, "site_ready": True, "site_ready_min": 420,
                         "load_plan_approved": True, "source_id": "HAND"} for i, start in ((1, 540), (2, 600))],
            "travel": {"location_ids": ["D", "L"], "distance_m": [[0, 10000], [10000, 0]],
                       "duration_upper_min": [[0, 30], [30, 0]], "mode": "STATIC_MATRIX",
                       "speed_bands": [], "source_id": "HAND"}}


def hand_plan(case):
    return {"schema_version": "1.0", "case_id": case["case_id"], "input_sha256": input_hash(case),
            "status": "FEASIBLE", "served_batch_ids": ["B1", "B2"], "deferred_batch_ids": [],
            "unserved_eligible_batch_ids": [], "routes": [{"vehicle_id": "V1", "departure_min": 510,
                "return_min": 650, "distance_m": 20000, "stops": [
                    {"batch_id": "B1", "arrival_min": 540, "start_min": 540, "end_min": 560},
                    {"batch_id": "B2", "arrival_min": 560, "start_min": 600, "end_min": 620}]}],
            "metrics": {"distance_m": 20000, "travel_min": 60, "waiting_min": 40,
                        "vehicles_used": 1, "served_components": 2, "deferred_components": 0}}


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.case = hand_case()
        self.plan = hand_plan(self.case)

    def input_code(self, code, status="INVALID_INPUT"):
        report = prepare_case(self.case)
        self.assertEqual(report["status"], status, report)
        self.assertIn(code, [e["code"] for e in report["issues"]], report)

    def plan_code(self, code):
        report = validate_plan(self.case, self.plan)
        self.assertFalse(report["valid"], report)
        self.assertIn(code, [e["code"] for e in report["issues"]], report)

    def test_hand_derived_route_and_metrics(self):
        report = validate_plan(self.case, self.plan)
        self.assertTrue(report["valid"], report)
        self.assertTrue(report["all_requested_served"])
        self.assertEqual(report["recomputed_metrics"], self.plan["metrics"])

    def test_saved_phase6_examples(self):
        for name, full in (("normal", True), ("static", True), ("readiness", False), ("no_work", False)):
            with self.subTest(name=name):
                case = read_json(HERE / "examples" / f"{name}.input.json")
                plan = read_json(HERE / "examples" / f"{name}.output.json")
                report = validate_plan(case, plan)
                self.assertTrue(report["valid"], report)
                self.assertEqual(report["all_requested_served"], full)

    def test_rejects_malformed_types_units_and_unknown_fields(self):
        changes = [lambda c: c["components"][0].update(weight_kg=True),
                   lambda c: c["components"][0].update(weight_kg=-1),
                   lambda c: c["components"][0].update(weight_kg=1000.5),
                   lambda c: c["units"].update(mass="tonne"),
                   lambda c: c["batches"][0].update(weight_kg=999),
                   lambda c: c["batches"][0].pop("site_ready"),
                   lambda c: c.update(schema_version="2.0")]
        for change in changes:
            case = hand_case()
            change(case)
            with self.subTest(case=case):
                self.assertEqual(prepare_case(case)["status"], "INVALID_INPUT")
        for malformed in (None, [], "bad", {"batches": []}):
            self.assertEqual(prepare_case(malformed)["status"], "INVALID_INPUT")

    def test_duplicate_component_id(self):
        self.case["components"][1]["component_id"] = "C1"
        self.input_code("DUPLICATE_ID")

    def test_duplicate_batch_id(self):
        self.case["batches"][1]["batch_id"] = "B1"
        self.input_code("DUPLICATE_ID")

    def test_unknown_component_reference(self):
        self.case["batches"][0]["component_ids"] = ["missing"]
        self.input_code("UNKNOWN_COMPONENT")

    def test_component_assigned_twice(self):
        self.case["batches"][1]["component_ids"] = ["C1"]
        self.input_code("COMPONENT_COVERAGE")

    def test_component_wrong_site(self):
        self.case["sites"].append({"site_id": "S2", "location_id": "L", "crane_id": "OTHER"})
        self.case["components"][0]["site_id"] = "S2"
        self.input_code("COMPONENT_SITE_MISMATCH")

    def test_missing_source_reference(self):
        self.case["components"][0]["source_id"] = "missing"
        self.input_code("UNKNOWN_SOURCE")

    def test_synthetic_not_mislabeled_measured(self):
        self.case["data_kind"] = "measured"
        self.input_code("PROVENANCE_CONFLICT")

    def test_matrix_size_and_location_mapping(self):
        self.case["travel"]["distance_m"] = [[0]]
        self.input_code("MATRIX_SHAPE")
        self.case = hand_case()
        self.case["depot"]["location_id"] = "missing"
        self.input_code("LOCATION_MAPPING")

    def test_matrix_diagonal(self):
        self.case["travel"]["distance_m"][0][0] = 1
        self.input_code("MATRIX_DIAGONAL")

    def test_batch_sequence_gap(self):
        self.case["batches"][1]["sequence"] = 3
        self.input_code("BATCH_SEQUENCE")

    def test_component_order_within_batches(self):
        self.case["components"][0]["installation_rank"] = 2
        self.case["components"][1]["installation_rank"] = 1
        self.input_code("COMPONENT_SEQUENCE")

    def test_overlapping_slots_are_unsupported_not_infeasible(self):
        self.case["batches"][1]["slot_start_min"] = 565
        self.input_code("OVERLAPPING_SEQUENCE_SLOTS", "UNSUPPORTED_INPUT")

    def test_shared_crane_is_unsupported(self):
        self.case["sites"].append({"site_id": "S2", "location_id": "L", "crane_id": "CRANE"})
        self.input_code("SHARED_CRANE", "UNSUPPORTED_INPUT")

    def test_unapproved_load_plan(self):
        self.case["batches"][0]["load_plan_approved"] = False
        self.input_code("LOAD_PLAN_REQUIRED", "UNSUPPORTED_INPUT")

    def test_readiness_cascades_and_does_not_mutate_input(self):
        self.case["components"][0]["production_ready"] = False
        before = copy.deepcopy(self.case)
        report = prepare_case(self.case)
        self.assertEqual(report["status"], "NO_ELIGIBLE_WORK")
        self.assertEqual(report["counts"]["deferred_components"], 2)
        self.assertEqual(report["deferred_batches"][1]["blocked_by_batch_id"], "B1")
        self.assertIn("PREDECESSOR_DEFERRED", report["deferred_batches"][1]["reason_codes"])
        self.assertEqual(self.case, before)

    def test_derive_mass_and_release_from_components(self):
        self.case["components"][1].update(weight_kg=1234, release_min=520)
        report = prepare_case(self.case)
        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["eligible_batches"][1]["demand_kg"], 1234)
        self.assertEqual(report["eligible_batches"][1]["release_min"], 520)
        self.assertEqual(report["eligible_batches"][1]["tw_late_min"], 610)

    def test_proven_batch_overweight(self):
        self.case["components"][0]["weight_kg"] = 3001
        self.input_code("BATCH_CAPACITY", "PROVEN_INFEASIBLE")

    def test_proven_single_trip_fleet_shortage(self):
        self.case["fleet"].update(capacity_kg=1500, vehicle_ids=["V1"])
        self.input_code("FLEET_CAPACITY", "PROVEN_INFEASIBLE")

    def test_proven_impossible_service_interval(self):
        self.case["batches"][0]["slot_end_min"] = 550
        self.input_code("IMPOSSIBLE_TIME_INTERVAL", "PROVEN_INFEASIBLE")

    def test_ready_does_not_claim_feasible_bin_packing(self):
        # Three indivisible 2,000 kg batches cannot fit two 3,000 kg vehicles,
        # but the aggregate necessary checks cannot prove that. READY is right.
        self.case["components"].append({**self.case["components"][-1], "component_id": "C3", "installation_rank": 3})
        for c in self.case["components"]:
            c["weight_kg"] = 2000
        self.case["batches"].append({**self.case["batches"][-1], "batch_id": "B3", "component_ids": ["C3"],
                                     "sequence": 3, "slot_start_min": 660, "slot_end_min": 690})
        self.assertEqual(prepare_case(self.case)["status"], "READY")

    def test_deferral_must_be_reported(self):
        case = read_json(HERE / "examples/readiness.input.json")
        plan = read_json(HERE / "examples/readiness.output.json")
        plan["deferred_batch_ids"] = []
        self.assertIn("DEFERRED_COVERAGE", [e["code"] for e in validate_plan(case, plan)["issues"]])

    def test_missing_batch(self):
        self.plan["routes"][0]["stops"].pop()
        self.plan["served_batch_ids"] = ["B1"]
        self.plan_code("BATCH_COVERAGE")

    def test_duplicate_batch_visit(self):
        self.plan["routes"][0]["stops"].append(copy.deepcopy(self.plan["routes"][0]["stops"][0]))
        self.plan["served_batch_ids"].append("B1")
        self.plan_code("BATCH_COVERAGE")

    def test_unknown_vehicle(self):
        self.plan["routes"][0]["vehicle_id"] = "V3"
        self.plan_code("VEHICLE_ASSIGNMENT")

    def test_vehicle_used_twice(self):
        self.plan["routes"].append(copy.deepcopy(self.plan["routes"][0]))
        self.plan_code("VEHICLE_ASSIGNMENT")

    def test_vehicle_capacity_for_whole_route(self):
        self.case["fleet"]["capacity_kg"] = 1500
        self.plan["input_sha256"] = input_hash(self.case)
        self.plan_code("CAPACITY")

    def test_release_applies_to_all_onboard_work(self):
        self.case["components"][1]["release_min"] = 520
        self.plan["input_sha256"] = input_hash(self.case)
        self.plan_code("PRODUCTION_RELEASE")

    def test_service_end_not_only_start_inside_slot(self):
        self.plan["routes"][0]["stops"][0].update(start_min=565, end_min=585)
        self.plan_code("CRANE_SLOT")

    def test_site_ready_time(self):
        self.case["batches"][0]["site_ready_min"] = 545
        self.plan["input_sha256"] = input_hash(self.case)
        self.plan_code("CRANE_SLOT")

    def test_arrival_recomputed(self):
        self.plan["routes"][0]["stops"][0]["arrival_min"] = 539
        self.plan_code("ARRIVAL_TIME")

    def test_service_duration_recomputed(self):
        self.plan["routes"][0]["stops"][0]["end_min"] = 550
        self.plan_code("SERVICE_DURATION")

    def test_return_leg_recomputed(self):
        self.plan["routes"][0]["return_min"] = 620
        self.plan_code("RETURN_TIME")

    def test_return_must_fit_shift(self):
        self.case["fleet"]["shift_end_min"] = 640
        self.plan["input_sha256"] = input_hash(self.case)
        self.plan_code("SHIFT_END")

    def test_total_distance_and_metrics_recomputed(self):
        self.plan["routes"][0]["distance_m"] = 1
        self.plan_code("ROUTE_DISTANCE")
        self.plan = hand_plan(self.case)
        self.plan["metrics"]["waiting_min"] = 0
        self.plan_code("METRICS_MISMATCH")

    def test_cross_vehicle_crane_and_sequence(self):
        self.plan["routes"] = [
            {"vehicle_id": "V1", "departure_min": 510, "return_min": 590, "distance_m": 20000,
             "stops": [{"batch_id": "B1", "arrival_min": 540, "start_min": 540, "end_min": 560}]},
            {"vehicle_id": "V2", "departure_min": 520, "return_min": 600, "distance_m": 20000,
             "stops": [{"batch_id": "B2", "arrival_min": 550, "start_min": 550, "end_min": 570}]}]
        self.plan_code("CRANE_OVERLAP")
        self.plan_code("INSTALLATION_SEQUENCE")

    def test_plan_is_bound_to_input_revision(self):
        self.case["case_id"] = "revision2"
        self.plan_code("INPUT_IDENTITY")

    def test_failure_report_does_not_claim_feasibility_or_zero_cost(self):
        self.plan.update(status="NO_FEASIBLE_SOLUTION_FOUND", routes=[], served_batch_ids=[],
                         unserved_eligible_batch_ids=["B1", "B2"], metrics=None)
        report = validate_plan(self.case, self.plan)
        self.assertTrue(report["valid"], report)
        self.assertFalse(report["feasible_for_eligible_work"])
        self.assertIsNone(report["recomputed_metrics"])
        self.plan["metrics"] = hand_plan(self.case)["metrics"]
        self.plan_code("FAILURE_ENVELOPE")

    def test_false_empty_success(self):
        self.plan.update(status="NO_ELIGIBLE_WORK", routes=[], served_batch_ids=[])
        self.plan_code("PLAN_STATUS")

    def test_fully_empty_request(self):
        self.case.update(components=[], batches=[])
        report = prepare_case(self.case)
        self.assertEqual(report["status"], "NO_ELIGIBLE_WORK")
        self.assertEqual(report["counts"]["requested_components"], 0)

    def test_asymmetric_distance_and_duration(self):
        self.case["travel"]["distance_m"][1][0] = 12000
        self.case["travel"]["duration_upper_min"][1][0] = 35
        self.plan["input_sha256"] = input_hash(self.case)
        self.plan["routes"][0].update(return_min=655, distance_m=22000)
        self.plan["metrics"].update(distance_m=22000, travel_min=65)
        self.assertTrue(validate_plan(self.case, self.plan)["valid"])

    def test_fifo_speed_boundary_and_day_end(self):
        self.case["travel"].update(mode="FIFO_SPEED_BANDS", speed_bands=[
            {"start_min": 0, "end_min": 540, "speed_kmh": 20},
            {"start_min": 540, "end_min": 1440, "speed_kmh": 40}])
        self.assertEqual(prepare_case(self.case)["status"], "READY")
        self.assertEqual(travel_minutes(self.case, "D", "L", 530), 20)
        self.assertEqual(travel_minutes(self.case, "D", "L", 540), 15)
        arrivals = [t + travel_minutes(self.case, "D", "L", t) for t in range(500, 561)]
        self.assertEqual(arrivals, sorted(arrivals))
        self.assertIsNone(travel_minutes(self.case, "D", "L", 1439))

    def test_incomplete_speed_profile(self):
        self.case["travel"].update(mode="FIFO_SPEED_BANDS", speed_bands=[
            {"start_min": 420, "end_min": 1440, "speed_kmh": 20}])
        self.input_code("SPEED_BAND_COVERAGE")

    def test_duration_upper_bound_is_conservative(self):
        self.case["travel"].update(mode="FIFO_SPEED_BANDS", speed_bands=[
            {"start_min": 0, "end_min": 1440, "speed_kmh": 20}])
        self.case["travel"]["duration_upper_min"][0][1] = 29
        self.input_code("NONCONSERVATIVE_DURATION")

    def test_strict_json_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "input.json"
            for text in ('{"weight":1,"weight":2}', '{"value":NaN}', '{"value":Infinity}'):
                p.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_json(p)


if __name__ == "__main__":
    unittest.main()
