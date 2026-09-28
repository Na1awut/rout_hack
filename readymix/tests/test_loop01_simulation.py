# Loop 1 unit, edge and failure tests.  Run:  python -m pytest readymix/tests -q
import csv
import hashlib
import json
import shutil

import pytest

from readymix.application.capacity_projection import build_instance
from readymix.application.data_validator import validate_dataset
from readymix.simulation.build_dataset import generate, load_configs, scenario_params, simulate
from readymix.simulation.world import split_trips


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    root = tmp_path_factory.mktemp("sim")
    return {n: generate(n, 42, root) for n in ("S0_normal", "S3_site_delay", "S6_high_demand",
                                              "S7_mixed_disruption", "S8_ai_prediction_error")}


def copy_dataset(src, tmp_path):
    dst = tmp_path / src.name
    shutil.copytree(src, dst)
    return dst


def rewrite(ds, rel, edit):
    """Edit a CSV and refresh its manifest hash, so only the content check can catch it."""
    p = ds / rel
    with open(p, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        cols, rows = r.fieldnames, list(r)
    cols, rows = edit(cols, rows)
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    m = json.loads((ds / "manifest.json").read_text(encoding="utf-8"))
    m["files"][rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    (ds / "manifest.json").write_text(json.dumps(m, indent=2), encoding="utf-8")


# -- trip split -------------------------------------------------------------

def test_split_properties_over_all_volumes():
    for k in range(8, 161):                                  # 4.0 .. 80.0 m3 in 0.5 steps
        v = k / 2
        trips = split_trips(v, 6.0, 0.25)
        assert abs(sum(trips) - v) < 1e-9
        assert max(trips) <= 6.0
        assert min(trips) > 3.0, (v, trips)                  # strictly above half a drum
        assert len(trips) == -(-k // 12)                     # ceil(v / 6)


@pytest.mark.parametrize("v,expected", [(4.0, [4.0]), (6.0, [6.0]), (6.5, [3.25, 3.25]),
                                        (12.0, [6.0, 6.0]), (12.5, [4.25, 4.25, 4.0])])
def test_split_edge_cases(v, expected):
    assert split_trips(v, 6.0, 0.25) == expected


# -- reproducibility and scenario isolation ----------------------------------

def test_same_seed_same_bytes(base, tmp_path):
    again = generate("S0_normal", 42, tmp_path)
    a = json.loads((base["S0_normal"] / "manifest.json").read_text(encoding="utf-8"))
    b = json.loads((again / "manifest.json").read_text(encoding="utf-8"))
    assert a["files"] == b["files"]


def test_different_seed_different_world(base, tmp_path):
    other = generate("S0_normal", 7, tmp_path)
    a = json.loads((base["S0_normal"] / "manifest.json").read_text(encoding="utf-8"))["files"]
    b = json.loads((other / "manifest.json").read_text(encoding="utf-8"))["files"]
    assert a["orders/orders.csv"] != b["orders/orders.csv"]


def test_scenarios_share_the_base_world(base):
    files = {n: json.loads((d / "manifest.json").read_text(encoding="utf-8"))["files"] for n, d in base.items()}
    for n in files:
        for rel in ("master/plants.csv", "master/vehicles.csv", "master/travel_profile.csv"):
            assert files[n][rel] == files["S0_normal"][rel], (n, rel)
        if n != "S6_high_demand":
            assert files[n]["master/sites.csv"] == files["S0_normal"]["master/sites.csv"], n

    # S6 adds orders, which may move a site's planned_ready_time (DERIVED from
    # its earliest order); every other site column must stay the same
    def sites(n):
        with open(base[n] / "master/sites.csv", encoding="utf-8", newline="") as f:
            return [{k: v for k, v in r.items() if k != "planned_ready_time"} for r in csv.DictReader(f)]
    assert sites("S6_high_demand") == sites("S0_normal")
    assert files["S3_site_delay"]["orders/orders.csv"] == files["S0_normal"]["orders/orders.csv"]
    assert files["S6_high_demand"]["orders/orders.csv"] != files["S0_normal"]["orders/orders.csv"]


def test_unknown_scenario_is_rejected():
    _, scen = load_configs()
    with pytest.raises(KeyError):
        scenario_params(scen, "S99_nope")


# -- scenario semantics -----------------------------------------------------

def test_events_match_scenario_definition():
    sim, scen = load_configs()
    for name, spec in scen["scenarios"].items():
        params, t = simulate(sim, scen, name, 42)
        ev = [e["event_type"] for e in t["runtime/events.json"]]
        assert ev.count("SITE_DELAY") == params["site_delays"], name
        assert ev.count("PUMP_FAILURE") == params["pump_failures"], name
        assert ev.count("TRAFFIC_SPIKE") == params["traffic_spikes"], name
        assert ev.count("TRUCK_BREAKDOWN") == params["truck_breakdowns"], name


def test_surprises_contradict_site_history():
    sim, scen = load_configs()
    _, t = simulate(sim, scen, "S8_ai_prediction_error", 42)
    cls = {s["site_id"]: s["reliability_class"] for s in t["ground_truth/site_traits.csv"]}
    for e in t["runtime/events.json"]:
        if e["event_type"] == "SITE_READY_LATE":
            assert cls[e["site_id"]] == "good"
        if e["event_type"] == "SITE_READY_EARLY":
            assert cls[e["site_id"]] == "poor"


def test_pump_failure_only_where_a_pump_exists():
    sim, scen = load_configs()
    _, t = simulate(sim, scen, "S5_pump_failure", 42)
    pump = {s["site_id"]: s["pump_available"] for s in t["master/sites.csv"]}
    assert all(pump[e["site_id"]] for e in t["runtime/events.json"] if e["event_type"] == "PUMP_FAILURE")


def test_site_delay_adds_to_that_order_only():
    sim, scen = load_configs()
    _, s0 = simulate(sim, scen, "S0_normal", 42)
    _, s3 = simulate(sim, scen, "S3_site_delay", 42)
    ev = [e for e in s3["runtime/events.json"] if e["event_type"] == "SITE_DELAY"][0]
    d0 = {r["order_id"]: r["ready_delay_min"] for r in s0["ground_truth/order_readiness.csv"]}
    d3 = {r["order_id"]: r["ready_delay_min"] for r in s3["ground_truth/order_readiness.csv"]}
    for oid in d0:
        assert d3[oid] == d0[oid] + (ev["delay_min"] if oid == ev["order_id"] else 0)


# -- validator: must pass clean data and catch every planted fault ----------

def test_clean_datasets_validate(base):
    for n, d in base.items():
        assert validate_dataset(d) == [], n


def test_catches_edit_without_manifest_update(base, tmp_path):
    ds = copy_dataset(base["S0_normal"], tmp_path)
    p = ds / "orders/orders.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("ACTIVE", "ACTlVE", 1), encoding="utf-8")
    assert any("sha256" in e for e in validate_dataset(ds))


@pytest.mark.parametrize("rel,edit,needle", [
    ("orders/orders.csv", lambda c, r: (c, [dict(r[0], site_id="S999")] + r[1:]), "unknown site"),
    ("orders/trips.csv", lambda c, r: (c, [dict(r[0], volume_m3="6.5")] + r[1:]), "does not fit"),
    ("orders/trips.csv", lambda c, r: (c, r[1:]), "do not sum"),
    ("runtime/traffic.csv", lambda c, r: (c, r[1:]), "does not cover"),
    ("master/travel_profile.csv", lambda c, r: (c, r[1:]), "every traffic hour"),
    ("runtime/traffic.csv", lambda c, r: (c, [dict(r[0], predicted_travel_min="1.0")] + r[1:]), "base x multiplier"),
    ("master/vehicles.csv", lambda c, r: (c, [dict(r[0], capacity_m3="8.0")] + r[1:]), "one capacity"),
    ("master/vehicles.csv", lambda c, r: (c, [dict(r[0], status="FLYING")] + r[1:]), "status"),
    ("master/sites.csv", lambda c, r: (c + ["secret"], [dict(x, secret="1") for x in r]), "no data_dictionary"),
    ("data_dictionary.csv", lambda c, r: (c, [dict(r[0], source_type="GUESS")] + r[1:]), "source_type"),
    ("ground_truth/order_readiness.csv", lambda c, r: (c, [dict(r[0], ready_delay_min="999")] + r[1:]), "actual - planned"),
])
def test_catches_planted_fault(base, tmp_path, rel, edit, needle):
    ds = copy_dataset(base["S0_normal"], tmp_path)
    rewrite(ds, rel, edit)
    problems = validate_dataset(ds)
    assert any(needle in e for e in problems), problems


# -- projection never touches labels ----------------------------------------

def test_projection_does_not_need_ground_truth(base, tmp_path):
    ds = copy_dataset(base["S0_normal"], tmp_path)
    shutil.rmtree(ds / "ground_truth")
    inst, node_trip = build_instance(ds)
    assert len(node_trip) == inst.dimension - 1
