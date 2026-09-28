# Loop 2 tests: hand-computed day, causality, validator faults, reproducibility
import copy
import csv
import json

import pytest

from readymix.application.dispatch_policies import ReactiveRule, StaticPlanned
from readymix.application.execution_validator import validate_execution
from readymix.application.kpi import compute_kpis
from readymix.simulation.executor import run_day


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def tiny_day(root, n_trucks=1, n_trips=2, ready="09:10", bays=1):
    """1 plant, 1 site 20 road-km away, 30 min travel every hour, 1 order."""
    D = "2026-10-01T"
    _write(root / "master/plants.csv", [dict(plant_id="P1", plant_name="p", latitude=13.0, longitude=100.0,
           loading_bays=bays, load_time_min=8, wash_time_min=10, operating_start="06:00", operating_end="18:00")])
    _write(root / "master/sites.csv", [dict(site_id="S1", latitude=13.1, longitude=100.0)])
    _write(root / "master/vehicles.csv", [dict(vehicle_id=f"T{i + 1}", capacity_m3=6.0, available_from=D + "06:00",
           fuel_efficiency_km_l=2.5, idle_fuel_l_h=3.0) for i in range(n_trucks)])
    _write(root / "orders/orders.csv", [dict(order_id="O1", site_id="S1", total_volume_m3=6.0 * n_trips,
           requested_start=D + "09:00", target_interval_min=20, estimated_unload_min=15)])
    _write(root / "orders/trips.csv", [dict(trip_id=f"O1-{k:02d}", order_id="O1", site_id="S1", seq=k, volume_m3=6.0,
           planned_arrival=D + f"{(540 + 20 * (k - 1)) // 60:02d}:{(540 + 20 * (k - 1)) % 60:02d}")
           for k in range(1, n_trips + 1)])
    edges = [("P1", "S1"), ("S1", "P1")]
    _write(root / "master/travel_profile.csv", [dict(from_node=a, to_node=b, hour=h, typical_travel_min=30.0)
                                                for a, b in edges for h in range(5, 20)])
    _write(root / "runtime/traffic.csv", [dict(from_node=a, to_node=b, timestamp=D + f"{h:02d}:00", road_km=20.0,
                                               predicted_travel_min=30.0) for a, b in edges for h in range(5, 20)])
    (root / "runtime/events.json").write_text("[]", encoding="utf-8")
    _write(root / "ground_truth/order_readiness.csv", [dict(order_id="O1", actual_ready_time=D + ready)])
    _write(root / "ground_truth/trip_service.csv", [dict(trip_id=f"O1-{k:02d}", actual_unload_min=15.0)
                                                    for k in range(1, n_trips + 1)])
    return root


def hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def test_hand_computed_static_day(tmp_path):
    root = tiny_day(tmp_path)
    r = run_day(root, StaticPlanned())
    l1, l2 = r["log"]["O1-01"], r["log"]["O1-02"]
    # trip 1: release floor5(09:00 - 30 - 8 = 08:22) = 08:20
    assert (l1["released"], l1["load_start"], l1["depart"], l1["arrive"]) == (hm("08:20"), hm("08:20"), hm("08:28"), hm("08:58"))
    assert (l1["unload_start"], l1["unload_end"], l1["back"], l1["free"]) == (hm("09:10"), hm("09:25"), hm("09:55"), hm("10:05"))
    # trip 2: released 08:40 but the only truck is back at 10:05
    assert (l2["released"], l2["load_start"], l2["arrive"]) == (hm("08:40"), hm("10:05"), hm("10:43"))
    assert (l2["unload_start"], l2["unload_end"], l2["free"]) == (hm("10:43"), hm("10:58"), hm("11:38"))
    assert validate_execution(r, root) == []
    k = compute_kpis(r, root)
    assert k["total_distance_km"] == 80.0
    assert k["total_waiting_min"] == 12                  # 08:58 -> 09:10
    assert k["site_idle_min"] == 78                      # 0 before the first load + 09:25 -> 10:43
    assert k["pour_gap_max_min"] == 78
    assert k["late_arrivals"] == 1 and k["on_time_rate"] == 0.5   # trip 2 due max(09:20, 09:10+20) = 09:30
    assert k["release_delay_min"] == 85                  # 08:40 -> 10:05
    assert k["fleet_utilization"] == round(2 * (8 + 30 + 15 + 30 + 10) / 720, 3)
    assert k["fuel_liters"] == round(80 / 2.5 + 12 / 60 * 3.0, 1)
    assert k["unserved_trips"] == 0


def test_reactive_holds_while_a_truck_waits(tmp_path):
    root = tiny_day(tmp_path, n_trucks=3, n_trips=3, ready="10:30")
    a = run_day(root, StaticPlanned())
    r = run_day(root, ReactiveRule())
    assert a["log"]["O1-03"]["released"] == hm("09:00")
    assert r["log"]["O1-03"]["released"] >= hm("10:30")          # held until the site's ready call
    assert compute_kpis(r, root)["total_waiting_min"] < compute_kpis(a, root)["total_waiting_min"]
    assert validate_execution(r, root) == [] and validate_execution(a, root) == []


def test_policies_cannot_see_the_future(tmp_path):
    """Moving the (unannounced) ready time later must not change any release
    decided before the earlier of the two ready times."""
    early = run_day(tiny_day(tmp_path / "a", n_trucks=3, n_trips=3, ready="10:30"), ReactiveRule())
    late = run_day(tiny_day(tmp_path / "b", n_trucks=3, n_trips=3, ready="11:30"), ReactiveRule())
    for tid in early["log"]:
        e, l = early["log"][tid].get("released"), late["log"][tid].get("released")
        if e is not None and e < hm("10:30"):
            assert e == l, tid
    for P in (StaticPlanned,):
        x = run_day(tmp_path / "a", P())
        y = run_day(tmp_path / "b", P())
        assert {k: v["released"] for k, v in x["log"].items()} == {k: v["released"] for k, v in y["log"].items()}


def test_same_input_same_log(tmp_path):
    root = tiny_day(tmp_path, n_trucks=2, n_trips=3)
    assert run_day(root, ReactiveRule())["log"] == run_day(root, ReactiveRule())["log"]


@pytest.mark.parametrize("tamper,needle", [
    (lambda lg: lg["O1-01"].update(unload_start=lg["O1-01"]["unload_start"] - 5), "before the site was ready"),
    (lambda lg: lg["O1-01"].update(arrive=lg["O1-01"]["arrive"] + 1), "outbound travel"),
    (lambda lg: lg["O1-02"].update(unload_end=lg["O1-02"]["unload_end"] + 3), "unload length"),
    (lambda lg: lg["O1-02"].update(truck="T1", load_start=lg["O1-01"]["load_start"] + 1,
                                   depart=lg["O1-01"]["load_start"] + 9), "overlap"),
    (lambda lg: lg["O1-02"].pop("unload_end"), "loaded but never delivered"),
])
def test_execution_validator_catches(tmp_path, tamper, needle):
    root = tiny_day(tmp_path, n_trucks=2, n_trips=2)
    r = run_day(root, StaticPlanned())
    assert validate_execution(r, root) == []
    bad = dict(r, log=copy.deepcopy(r["log"]))
    tamper(bad["log"])
    assert any(needle in p for p in validate_execution(bad, root)), validate_execution(bad, root)


def test_breakdown_takes_truck_out(tmp_path):
    root = tiny_day(tmp_path, n_trucks=2, n_trips=3)
    (root / "runtime/events.json").write_text(json.dumps([{"event_id": "E1", "timestamp": "2026-10-01T06:00",
                                                           "event_type": "TRUCK_BREAKDOWN", "vehicle_id": "T1"}]))
    r = run_day(root, StaticPlanned())
    assert all(lg.get("truck") != "T1" for lg in r["log"].values())
    assert validate_execution(r, root) == []
