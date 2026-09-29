# impact.py -- Loop 8: execution log -> fuel, CO2 and THB (skill.md section 17)
"""Recomputes the fuel and idle quantities from the raw log and dataset
instead of trusting kpi.py, so run_loop08 can cross-check the two.

moving fuel   2 x road km (plant <-> site) / truck km_per_l, delivered trips
idle fuel     (unload_start - arrive) / 60 x truck idle_l_per_h
driver wait   the same waiting minutes, in hours
crew idle     per order, site idle minutes x crew size of the order's site
CO2           fuel x diesel_co2_kg_per_liter (factor lives in impact.yaml)
"""
import csv
from pathlib import Path

import yaml

IMPACT_CFG = Path(__file__).resolve().parents[1] / "config" / "impact.yaml"
CASES = ("value", "low", "high")


def _rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _hhmm(iso):
    h, m = iso[11:16].split(":")
    return int(h) * 60 + int(m)


def load_factors(path=IMPACT_CFG) -> dict:
    """{case: {name: number}} for the monetised/carbon factors."""
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    items = {"co2_kg_per_l": cfg["carbon"]["diesel_co2_kg_per_liter"],
             "diesel_thb_per_l": cfg["fuel"]["diesel_price_thb_per_liter"],
             "driver_thb_per_h": cfg["labor"]["driver_cost_thb_per_hour"],
             "crew_thb_per_person_h": cfg["labor"]["crew_cost_thb_per_person_hour"]}
    out = {case: {k: float(v.get(case, v["value"])) for k, v in items.items()} for case in CASES}
    for case in CASES:
        out[case]["days_per_year"] = float(cfg["annualization"]["operating_days_per_year"]["value"])
    return out


def breakdown(log: dict, dataset_root) -> dict:
    """Physical quantities of one executed day, independent of kpi.py."""
    root = Path(dataset_root)
    trips = {t["trip_id"]: t for t in _rows(root / "orders/trips.csv")}
    orders = {o["order_id"]: o for o in _rows(root / "orders/orders.csv")}
    crew = {s["site_id"]: int(s["crew_size"]) for s in _rows(root / "master/sites.csv")}
    veh = {v["vehicle_id"]: v for v in _rows(root / "master/vehicles.csv")}
    ready = {r["order_id"]: _hhmm(r["actual_ready_time"]) for r in _rows(root / "ground_truth/order_readiness.csv")}
    plant = _rows(root / "master/plants.csv")[0]["plant_id"]
    road = {r["to_node"]: float(r["road_km"]) for r in _rows(root / "runtime/traffic.csv") if r["from_node"] == plant}

    moving = idle = wait_min = km = m3 = 0.0
    by_order = {}
    for tid, lg in log.items():
        if "unload_end" not in lg:
            continue
        t = trips[tid]
        v = veh[lg["truck"]]
        d = 2 * road[t["site_id"]]
        w = lg["unload_start"] - lg["arrive"]
        km += d
        moving += d / float(v["fuel_efficiency_km_l"])
        idle += w / 60 * float(v["idle_fuel_l_h"])
        wait_min += w
        m3 += float(t["volume_m3"])
        by_order.setdefault(t["order_id"], []).append(lg)
    crew_person_h = site_idle_min = 0.0
    for oid, lgs in by_order.items():
        lgs.sort(key=lambda l: l["unload_start"])
        order_idle = max(0, lgs[0]["unload_start"] - ready[oid])
        order_idle += sum(b["unload_start"] - a["unload_end"] for a, b in zip(lgs, lgs[1:]))
        site_idle_min += order_idle
        crew_person_h += order_idle / 60 * crew[orders[oid]["site_id"]]
    return dict(distance_km=km, moving_fuel_l=moving, idle_fuel_l=idle, fuel_l=moving + idle,
                driver_wait_h=wait_min / 60, site_idle_min=site_idle_min, crew_idle_person_h=crew_person_h,
                delivered_m3=m3)


def monetize(b: dict, f: dict) -> dict:
    """Daily CO2 and cost proxy for one breakdown under one factor case."""
    fuel_thb = b["fuel_l"] * f["diesel_thb_per_l"]
    driver_thb = b["driver_wait_h"] * f["driver_thb_per_h"]
    crew_thb = b["crew_idle_person_h"] * f["crew_thb_per_person_h"]
    return dict(co2_kg=b["fuel_l"] * f["co2_kg_per_l"], idle_co2_kg=b["idle_fuel_l"] * f["co2_kg_per_l"],
                fuel_thb=fuel_thb, driver_wait_thb=driver_thb, crew_idle_thb=crew_thb,
                cost_proxy_thb=fuel_thb + driver_thb + crew_thb)
