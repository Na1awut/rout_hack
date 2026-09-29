# execution_validator.py -- is an executed day physically possible?
"""Re-checks an execution log against the dataset files, without using the
engine's code paths. validate_execution(result, root) -> list of problems.

  each trip: timestamps in order; travel = realized slot value (rounded);
             unload never before the site is really ready; unload length
             = actual unload (rounded); loaded inside plant hours
  each truck: one trip at a time; not before available_from; no load after
             its breakdown
  each order: one discharge at a time
  plant:     never more trucks loading than loading bays
  volume:    delivered + unserved = ordered
"""

import csv
import json
from datetime import datetime
from pathlib import Path


def _rows(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _m(iso):
    d = datetime.fromisoformat(iso)
    return d.hour * 60 + d.minute


def validate_execution(result, root) -> list:
    root = Path(root)
    log = result["log"]
    problems = []
    err = problems.append

    plant = _rows(root / "master/plants.csv")[0]
    pid = plant["plant_id"]
    open_, close = _m("2000-01-01T" + plant["operating_start"]), _m("2000-01-01T" + plant["operating_end"])
    load, wash, bays = int(float(plant["load_time_min"])), int(float(plant["wash_time_min"])), int(plant["loading_bays"])
    avail = {v["vehicle_id"]: _m(v["available_from"]) for v in _rows(root / "master/vehicles.csv")}
    capacity = {v["vehicle_id"]: float(v["capacity_m3"]) for v in _rows(root / "master/vehicles.csv")}
    trips = {t["trip_id"]: t for t in _rows(root / "orders/trips.csv")}
    traffic = {}
    for r in _rows(root / "runtime/traffic.csv"):
        traffic[(r["from_node"], r["to_node"], int(r["timestamp"][11:13]))] = float(r["predicted_travel_min"])
    hours = sorted({h for (_, _, h) in traffic})
    ready = {r["order_id"]: _m(r["actual_ready_time"]) for r in _rows(root / "ground_truth/order_readiness.csv")}
    unload = {r["trip_id"]: float(r["actual_unload_min"]) for r in _rows(root / "ground_truth/trip_service.csv")}
    breaks = {e["vehicle_id"]: _m(e["timestamp"]) for e in json.loads((root / "runtime/events.json").read_text(encoding="utf-8"))
              if e["event_type"] == "TRUCK_BREAKDOWN"}

    def slot(frm, to, t):
        return traffic[(frm, to, min(max(t // 60, hours[0]), hours[-1]))]

    per_truck, per_order, loads = {}, {}, []
    delivered_vol = unserved_vol = 0.0
    if set(log) != set(trips):
        err("log does not cover exactly the dataset's trips")
    for tid, lg in log.items():
        tr = trips[tid]
        vol = float(tr["volume_m3"])
        if "unload_end" not in lg:
            unserved_vol += vol
            if "load_start" in lg:
                err(f"{tid}: loaded but never delivered")
            continue
        delivered_vol += vol
        seq = [lg["released"], lg["load_start"], lg["depart"], lg["arrive"], lg["unload_start"],
               lg["unload_end"], lg["back"], lg["free"]]
        if seq != sorted(seq):
            err(f"{tid}: timestamps out of order {seq}")
        if lg["depart"] - lg["load_start"] != load:
            err(f"{tid}: load time {lg['depart'] - lg['load_start']} != {load}")
        if not open_ <= lg["load_start"] < close:
            err(f"{tid}: loaded outside plant hours")
        if lg["arrive"] - lg["depart"] != max(1, round(slot(pid, tr["site_id"], lg["depart"]))):
            err(f"{tid}: outbound travel does not match traffic.csv")
        if lg["back"] - lg["unload_end"] != max(1, round(slot(tr["site_id"], pid, lg["unload_end"]))):
            err(f"{tid}: return travel does not match traffic.csv")
        if lg["unload_start"] < ready[tr["order_id"]]:
            err(f"{tid}: unloaded before the site was ready")
        if lg["unload_end"] - lg["unload_start"] != max(1, round(unload[tid])):
            err(f"{tid}: unload length does not match trip_service.csv")
        if lg["free"] - lg["back"] != wash:
            err(f"{tid}: wash time {lg['free'] - lg['back']} != {wash}")
        v = lg["truck"]
        if vol > capacity[v] + 1e-6:
            err(f"{tid}: load exceeds truck capacity")
        if lg["load_start"] < avail[v]:
            err(f"{tid}: {v} used before available_from")
        if v in breaks and lg["load_start"] >= breaks[v]:
            err(f"{tid}: {v} loaded after its breakdown")
        per_truck.setdefault(v, []).append((lg["load_start"], lg["free"], tid))
        per_order.setdefault(tr["order_id"], []).append((lg["unload_start"], lg["unload_end"], tid))
        loads.append((lg["load_start"], lg["depart"]))

    for key, spans in list(per_truck.items()) + list(per_order.items()):
        spans.sort()
        for (a0, a1, ta), (b0, b1, tb) in zip(spans, spans[1:]):
            if b0 < a1:
                err(f"{key}: {ta} and {tb} overlap")
    for t in sorted({s for s, _ in loads}):
        if sum(s <= t < e for s, e in loads) > bays:
            err(f"plant: more than {bays} trucks loading at minute {t}")
    total = sum(float(t["volume_m3"]) for t in trips.values())
    if abs(delivered_vol + unserved_vol - total) > 1e-6:
        err("volume not conserved")
    return problems
