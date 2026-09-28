import csv

import pytest

from readymix.application.impact import breakdown, load_factors, monetize


def _csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


@pytest.fixture
def day(tmp_path):
    _csv(tmp_path / "master/plants.csv", [dict(plant_id="P1")])
    _csv(tmp_path / "master/sites.csv", [dict(site_id="S1", crew_size=10)])
    _csv(tmp_path / "master/vehicles.csv", [dict(vehicle_id="T1", fuel_efficiency_km_l=2.5, idle_fuel_l_h=3.0)])
    _csv(tmp_path / "runtime/traffic.csv", [dict(from_node="P1", to_node="S1", road_km=10.0)])
    _csv(tmp_path / "orders/orders.csv", [dict(order_id="O1", site_id="S1")])
    _csv(tmp_path / "orders/trips.csv", [dict(trip_id="O1-01", order_id="O1", site_id="S1", volume_m3=5.0),
                                         dict(trip_id="O1-02", order_id="O1", site_id="S1", volume_m3=5.0),
                                         dict(trip_id="O1-03", order_id="O1", site_id="S1", volume_m3=5.0)])
    _csv(tmp_path / "ground_truth/order_readiness.csv", [dict(order_id="O1", actual_ready_time="2026-10-01T08:00")])
    log = {"O1-01": dict(truck="T1", arrive=470, unload_start=490, unload_end=510),   # waits 20, site idle 10
           "O1-02": dict(truck="T1", arrive=520, unload_start=520, unload_end=540),   # gap 10
           "O1-03": dict(truck="T1", arrive=600)}                                     # never unloaded
    return tmp_path, log


def test_breakdown_by_hand(day):
    root, log = day
    b = breakdown(log, root)
    assert b["distance_km"] == 40                       # 2 delivered x 2 x 10 km
    assert b["moving_fuel_l"] == pytest.approx(16)      # 40 / 2.5
    assert b["idle_fuel_l"] == pytest.approx(1)         # 20 min x 3 L/h
    assert b["driver_wait_h"] == pytest.approx(1 / 3)
    assert b["site_idle_min"] == 20                     # 10 before first + 10 gap
    assert b["crew_idle_person_h"] == pytest.approx(20 / 60 * 10)
    assert b["delivered_m3"] == 10


def test_monetize_by_hand(day):
    root, log = day
    f = dict(co2_kg_per_l=2.5, diesel_thb_per_l=40, driver_thb_per_h=150, crew_thb_per_person_h=50)
    m = monetize(breakdown(log, root), f)
    assert m["co2_kg"] == pytest.approx(17 * 2.5)
    assert m["idle_co2_kg"] == pytest.approx(2.5)
    assert m["cost_proxy_thb"] == pytest.approx(17 * 40 + 150 / 3 + 50 * 10 / 3)


def test_factor_cases_have_sources_and_order():
    f = load_factors()
    assert f["low"]["co2_kg_per_l"] < f["value"]["co2_kg_per_l"] < f["high"]["co2_kg_per_l"]
    assert f["value"]["co2_kg_per_l"] == pytest.approx(74100 * 43.0e-3 * 0.84 / 1000, abs=5e-4)
    import yaml
    from readymix.application.impact import IMPACT_CFG
    cfg = yaml.safe_load(IMPACT_CFG.read_text(encoding="utf-8"))
    for group in ("carbon", "fuel", "labor", "annualization"):
        for name, item in cfg[group].items():
            if isinstance(item, dict):
                assert item["source_type"] in {"PUBLIC_SOURCE", "DERIVED", "ASSUMED"}, name
                assert item.get("source") or item.get("derivation") or item.get("note"), name
