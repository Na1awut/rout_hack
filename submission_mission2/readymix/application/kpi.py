# kpi.py -- day KPIs from an execution log (skill.md section 18)
"""Definitions (the ASSUMED ones are marked; later loops may revisit them):

truck_wait_site_min   unload_start - arrive, summed over delivered trips
                      (drum turning, engine idling)
site_idle_min         per order: max(0, first unload start - actual ready)
                      + every gap between one unload's end and the next
                      unload's start -- the crew and pump stand idle
pour_gap_max_min      largest single gap between consecutive unloads
due time of trip k    max(planned arrival_k, actual ready + (k-1) x interval):
                      a site that is late itself moves its own schedule
on_time               unload_start <= due + 15 min (ASSUMED tolerance);
                      unserved trips count as not on time
release_delay_min     load_start - released: time a released load waited at
                      the plant for a truck or a bay
fleet_utilization     busy truck minutes (load, travel, unload, wash; not
                      waiting) / truck minutes available in plant hours
fuel_liters           km / km_per_l + site waiting hours x idle_l_per_h
                      (both truck figures are ASSUMED placeholders)
co2_kg                None: the emission factor is TBD_SOURCE (skill.md 17)
"""

import math

ON_TIME_TOLERANCE_MIN = 15


def compute_kpis(result, dataset_root) -> dict:
    from readymix.simulation.dataset import load_truth, _rows
    from pathlib import Path

    p = result["plan"]
    log = result["log"]
    truth = load_truth(dataset_root)
    road = {r["to_node"]: float(r["road_km"]) for r in _rows(Path(dataset_root) / "runtime/traffic.csv")
            if r["from_node"] == p.plant["plant_id"]}
    veh = {v["vehicle_id"]: v for v in p.vehicles}

    delivered = [t for t in p.trips if "unload_end" in log[t["trip_id"]]]
    unserved = [t for t in p.trips if "unload_end" not in log[t["trip_id"]]]
    km = sum(2 * road[t["site_id"]] for t in delivered)
    travel = sum(log[t["trip_id"]]["travel_out"] + log[t["trip_id"]]["travel_back"] for t in delivered)
    wait = sum(log[t["trip_id"]]["unload_start"] - log[t["trip_id"]]["arrive"] for t in delivered)
    rel_delay = sum(log[t["trip_id"]]["load_start"] - log[t["trip_id"]]["released"] for t in delivered)

    idle, gap_max, late, gaps_over_30 = 0, 0, 0, 0
    by_order = {}
    for t in delivered:
        by_order.setdefault(t["order_id"], []).append(log[t["trip_id"]])
    for oid, lgs in by_order.items():
        lgs.sort(key=lambda l: l["unload_start"])
        idle += max(0, lgs[0]["unload_start"] - truth.ready_min[oid])
        for a, b in zip(lgs, lgs[1:]):
            g = b["unload_start"] - a["unload_end"]
            idle += g
            gap_max = max(gap_max, g)
            gaps_over_30 += g > 30
    for t in p.trips:
        lg = log[t["trip_id"]]
        o = p.orders[t["order_id"]]
        due = max(t["planned_arrival_min"],
                  truth.ready_min[t["order_id"]] + (t["seq"] - 1) * int(o["target_interval_min"]))
        if "unload_start" not in lg or lg["unload_start"] > due + ON_TIME_TOLERANCE_MIN:
            late += 1

    busy = sum(p.load_min + lg["travel_out"] + lg["unload_dur"] + lg["travel_back"] + p.wash_min
               for lg in (log[t["trip_id"]] for t in delivered))
    have = sum(max(0, p.close_min - max(p.open_min, v["available_from_min"])) for v in p.vehicles)
    fuel = 0.0
    for t in delivered:
        lg = log[t["trip_id"]]
        v = veh[lg["truck"]]
        fuel += 2 * road[t["site_id"]] / float(v["fuel_efficiency_km_l"])
        fuel += (lg["unload_start"] - lg["arrive"]) / 60 * float(v["idle_fuel_l_h"])
    used = {log[t["trip_id"]]["truck"] for t in delivered}
    last_back = max((log[t["trip_id"]]["free"] for t in delivered), default=p.open_min)
    n = len(p.trips)
    return {
        "trips": n, "delivered_trips": len(delivered), "unserved_trips": len(unserved),
        "delivered_volume_m3": round(sum(float(t["volume_m3"]) for t in delivered), 2),
        "unserved_volume_m3": round(sum(float(t["volume_m3"]) for t in unserved), 2),
        "total_distance_km": round(km, 1),
        "total_travel_min": travel,
        "total_waiting_min": wait,
        "average_waiting_min": round(wait / len(delivered), 1) if delivered else math.nan,
        "site_idle_min": idle,
        "pour_gap_max_min": gap_max,
        "pour_gaps_over_30": gaps_over_30,
        "late_arrivals": late,
        "on_time_rate": round(1 - late / n, 3) if n else math.nan,
        "release_delay_min": rel_delay,
        "fleet_utilization": round(busy / have, 3) if have else 0.0,   # no truck on shift (Loop 9)
        "trucks_used": len(used),
        "trips_per_vehicle": round(len(delivered) / len(used), 2) if used else 0,
        "fuel_liters": round(fuel, 1),
        "co2_kg": None,
        "last_truck_free": f"{last_back // 60:02d}:{last_back % 60:02d}",
        "solver_runtime_ms": result["policy_runtime_ms"],
    }
