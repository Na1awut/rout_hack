# stats.py -- describe a generated dataset (Loop 1 "Measure" step)
"""fleet_load_ratio = truck-minutes the planned trips need / truck-minutes
the fleet has. A trip needs load + travel out + planned unload + travel
back + wash, with travel taken from the traffic slot of its planned
arrival hour. It ignores waiting, so it is a lower bound on real load:
a ratio near 1 already means the plan cannot be met.
"""

import csv
import json
from collections import Counter
from pathlib import Path

from .common import hhmm_to_min, iso_to_min


def _rows(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def dataset_stats(dataset_dir) -> dict:
    root = Path(dataset_dir)
    plant = _rows(root / "master/plants.csv")[0]
    vehicles = _rows(root / "master/vehicles.csv")
    orders = {o["order_id"]: o for o in _rows(root / "orders/orders.csv")}
    trips = _rows(root / "orders/trips.csv")
    traffic = {(r["from_node"], r["to_node"], r["timestamp"][11:13]): float(r["predicted_travel_min"])
               for r in _rows(root / "runtime/traffic.csv")}
    ready = _rows(root / "ground_truth/order_readiness.csv")
    service = _rows(root / "ground_truth/trip_service.csv")
    events = json.loads((root / "runtime/events.json").read_text(encoding="utf-8"))

    pid = plant["plant_id"]
    need = 0.0
    for t in trips:
        hh = t["planned_arrival"][11:13]
        o = orders[t["order_id"]]
        need += (float(plant["load_time_min"]) + traffic[(pid, t["site_id"], hh)] + float(o["estimated_unload_min"])
                 + traffic[(t["site_id"], pid, hh)] + float(plant["wash_time_min"]))
    open_, close = hhmm_to_min(plant["operating_start"]), hhmm_to_min(plant["operating_end"])
    have = sum(close - max(open_, iso_to_min(v["available_from"])) for v in vehicles)

    delays = [int(r["ready_delay_min"]) for r in ready]
    day_mult = [float(r["traffic_multiplier"]) for r in _rows(root / "runtime/traffic.csv")
                if 7 <= int(r["timestamp"][11:13]) < 18]
    ratio = [float(s["actual_unload_min"]) / float(s["estimated_unload_min"]) for s in service]
    ev = Counter(e["event_type"] for e in events)
    return {
        "orders": len(orders), "trips": len(trips),
        "volume_m3": round(sum(float(o["total_volume_m3"]) for o in orders.values()), 2),
        "trips_per_order": round(len(trips) / len(orders), 2),
        "fleet_load_ratio": round(need / have, 3),
        "mean_ready_delay_min": round(sum(delays) / len(delays), 1),
        "share_delay_gt15": round(sum(d > 15 for d in delays) / len(delays), 3),
        "max_ready_delay_min": max(delays),
        "mean_traffic_multiplier_7_18": round(sum(day_mult) / len(day_mult), 3),
        "mean_unload_actual_over_est": round(sum(ratio) / len(ratio), 3),
        "events": sum(ev.values()),
        "event_types": ";".join(f"{k}:{v}" for k, v in sorted(ev.items())),
    }
