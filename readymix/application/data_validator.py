# data_validator.py -- checks a dataset folder before anything consumes it
"""Independent of the generator: it reads the files back from disk and
re-derives what must hold, instead of trusting the code that wrote them.

validate_dataset(path) -> list of problems ([] = PASS). Checks:
  integrity   every file in manifest.json exists and matches its sha256
  dictionary  every column / event key has one data_dictionary.csv entry
              with a valid source_type; ASSUMED rows carry a note
  schema      ids unique, foreign keys resolve, enums and ranges hold
  consistency trips sum to their order, every trip fits a truck,
              traffic covers every plant-site edge for every hour and
              predicted = base x multiplier, one readiness label per order
"""

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

from readymix.simulation.data_dictionary import SOURCE_TYPES

TRUCK_STATUS = {"AVAILABLE", "LOADING", "EN_ROUTE", "WAITING", "UNLOADING", "RETURNING", "UNAVAILABLE"}
ORDER_STATUS = {"ACTIVE", "COMPLETED", "CANCELLED"}
EVENT_TYPES = {"SITE_DELAY", "TRAFFIC_SPIKE", "PUMP_FAILURE", "SERVICE_SLOWDOWN", "TRUCK_BREAKDOWN",
               "DEMAND_CHANGE", "SITE_READY_EARLY", "SITE_READY_LATE"}
EPS = 1e-6


def _read_csv(p):
    with open(p, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        return r.fieldnames or [], list(r)


def _dt(s):
    return datetime.fromisoformat(s)


def validate_dataset(path) -> list:
    root = Path(path)
    problems = []
    err = problems.append

    # -- integrity -------------------------------------------------------
    mp = root / "manifest.json"
    if not mp.exists():
        return ["manifest.json missing"]
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    for rel, digest in manifest["files"].items():
        f = root / rel
        if not f.exists():
            err(f"{rel}: missing")
        elif hashlib.sha256(f.read_bytes()).hexdigest() != digest:
            err(f"{rel}: sha256 does not match manifest (file changed after generation)")
    if problems:
        return problems

    # -- dictionary --------------------------------------------------------
    _, dd = _read_csv(root / "data_dictionary.csv")
    entries = {}
    for d in dd:
        key = (d["file"], d["field"])
        if key in entries:
            err(f"data_dictionary: duplicate entry {key}")
        entries[key] = d
        if d["source_type"] not in SOURCE_TYPES:
            err(f"data_dictionary: {key} has source_type {d['source_type']!r}")
        if d["source_type"] in ("ASSUMED", "PUBLIC_SOURCE") and not d["source"].strip():
            err(f"data_dictionary: {key} is {d['source_type']} but has no source/note")

    tables = {}
    for rel in manifest["files"]:
        if rel.endswith(".csv") and rel != "data_dictionary.csv":
            cols, rows = _read_csv(root / rel)
            tables[rel] = rows
            for c in cols:
                if (rel, c) not in entries:
                    err(f"{rel}: column {c!r} has no data_dictionary entry")
    events = json.loads((root / "runtime/events.json").read_text(encoding="utf-8"))
    for e in events:
        for k in e:
            if ("runtime/events.json", k) not in entries:
                err(f"events.json: key {k!r} has no data_dictionary entry")

    # -- schema ------------------------------------------------------------
    def unique(rel, key):
        ids = [r[key] for r in tables[rel]]
        if len(ids) != len(set(ids)):
            err(f"{rel}: duplicate {key}")
        return set(ids)

    plants = unique("master/plants.csv", "plant_id")
    sites = unique("master/sites.csv", "site_id")
    vehicles = unique("master/vehicles.csv", "vehicle_id")
    orders = unique("orders/orders.csv", "order_id")
    unique("orders/trips.csv", "trip_id")
    if len(plants) != 1:
        err(f"plants.csv: V1 supports exactly one plant, found {len(plants)}")

    for s in tables["master/sites.csv"]:
        if not (-90 <= float(s["latitude"]) <= 90 and -180 <= float(s["longitude"]) <= 180):
            err(f"sites.csv {s['site_id']}: bad coordinates")
        if not 1 <= int(s["site_priority"]) <= 5:
            err(f"sites.csv {s['site_id']}: site_priority out of 1-5")
        if s["pump_available"] not in ("true", "false"):
            err(f"sites.csv {s['site_id']}: pump_available not a bool")
        if float(s["historical_delay_std"]) < 0:
            err(f"sites.csv {s['site_id']}: negative historical_delay_std")

    caps = set()
    for v in tables["master/vehicles.csv"]:
        caps.add(float(v["capacity_m3"]))
        if float(v["capacity_m3"]) <= 0:
            err(f"vehicles.csv {v['vehicle_id']}: capacity must be > 0")
        if v["plant_id"] not in plants:
            err(f"vehicles.csv {v['vehicle_id']}: unknown plant {v['plant_id']}")
        if v["status"] not in TRUCK_STATUS:
            err(f"vehicles.csv {v['vehicle_id']}: status {v['status']!r}")
        if float(v["fuel_efficiency_km_l"]) <= 0 or float(v["idle_fuel_l_h"]) < 0:
            err(f"vehicles.csv {v['vehicle_id']}: fuel figures out of range")
    if len(caps) > 1:
        err(f"vehicles.csv: V1 core needs one capacity, found {sorted(caps)}")
    cap = min(caps) if caps else 0

    plant = tables["master/plants.csv"][0] if tables["master/plants.csv"] else None
    order_rows = {}
    for o in tables["orders/orders.csv"]:
        order_rows[o["order_id"]] = o
        if o["site_id"] not in sites:
            err(f"orders.csv {o['order_id']}: unknown site {o['site_id']}")
        if not float(o["total_volume_m3"]) > 0:
            err(f"orders.csv {o['order_id']}: volume must be > 0")
        if abs(float(o["remaining_volume_m3"]) - float(o["total_volume_m3"])) > EPS:
            err(f"orders.csv {o['order_id']}: remaining != total at start of day")
        if not _dt(o["requested_start"]) < _dt(o["requested_end"]):
            err(f"orders.csv {o['order_id']}: requested_start not before requested_end")
        if plant and not (plant["operating_start"] <= o["requested_start"][11:] <= plant["operating_end"]):
            err(f"orders.csv {o['order_id']}: requested_start outside plant hours")
        if int(o["target_interval_min"]) <= 0 or int(o["estimated_unload_min"]) <= 0:
            err(f"orders.csv {o['order_id']}: interval and unload must be > 0")
        if not 1 <= int(o["priority"]) <= 5:
            err(f"orders.csv {o['order_id']}: priority out of 1-5")
        if o["status"] not in ORDER_STATUS:
            err(f"orders.csv {o['order_id']}: status {o['status']!r}")

    # -- consistency -------------------------------------------------------
    per_order = {}
    for t in tables["orders/trips.csv"]:
        if t["order_id"] not in orders:
            err(f"trips.csv {t['trip_id']}: unknown order {t['order_id']}")
            continue
        o = order_rows[t["order_id"]]
        if t["site_id"] != o["site_id"]:
            err(f"trips.csv {t['trip_id']}: site differs from its order")
        vol = float(t["volume_m3"])
        if not 0 < vol <= cap + EPS:
            err(f"trips.csv {t['trip_id']}: volume {vol} does not fit capacity {cap}")
        per_order.setdefault(t["order_id"], []).append(vol)
    for oid, o in order_rows.items():
        if abs(sum(per_order.get(oid, [])) - float(o["total_volume_m3"])) > EPS:
            err(f"trips.csv: trips of {oid} do not sum to its volume")

    edges = {}
    for r in tables["runtime/traffic.csv"]:
        if r["from_node"] not in plants | sites or r["to_node"] not in plants | sites:
            err(f"traffic.csv: unknown node in {r['from_node']}->{r['to_node']}")
        m = float(r["traffic_multiplier"])
        if m <= 0:
            err(f"traffic.csv: non-positive multiplier {r['from_node']}->{r['to_node']} {r['timestamp']}")
        if abs(float(r["base_travel_min"]) * m - float(r["predicted_travel_min"])) > 0.02:
            err(f"traffic.csv: predicted != base x multiplier {r['from_node']}->{r['to_node']} {r['timestamp']}")
        edges.setdefault((r["from_node"], r["to_node"]), set()).add(r["timestamp"])
    slots = set().union(*edges.values()) if edges else set()
    for p in plants:
        for s in sites:
            for e in ((p, s), (s, p)):
                if edges.get(e) != slots:
                    err(f"traffic.csv: edge {e[0]}->{e[1]} does not cover every hour slot")

    prof = {}
    for r in tables["master/travel_profile.csv"]:
        if float(r["typical_travel_min"]) <= 0:
            err(f"travel_profile.csv: non-positive travel {r['from_node']}->{r['to_node']} h{r['hour']}")
        prof.setdefault((r["from_node"], r["to_node"]), set()).add(int(r["hour"]))
    hours = {int(s[11:13]) for s in slots}
    for p in plants:
        for s in sites:
            for e in ((p, s), (s, p)):
                if prof.get(e) != hours:
                    err(f"travel_profile.csv: edge {e[0]}->{e[1]} does not cover every traffic hour")

    labels = [r["order_id"] for r in tables["ground_truth/order_readiness.csv"]]
    if sorted(labels) != sorted(orders):
        err("order_readiness.csv: needs exactly one label per order")
    for r in tables["ground_truth/order_readiness.csv"]:
        delay = (_dt(r["actual_ready_time"]) - _dt(r["planned_ready_time"])).total_seconds() / 60
        if abs(delay - int(r["ready_delay_min"])) > EPS:
            err(f"order_readiness.csv {r['order_id']}: ready_delay_min != actual - planned")
    actual = {r["order_id"]: _dt(r["actual_ready_time"]) for r in tables["ground_truth/order_readiness.csv"]}
    for r in tables.get("runtime/site_state.csv", []):
        if r["order_id"] not in orders or r["site_id"] != order_rows[r["order_id"]]["site_id"]:
            err(f"site_state.csv: bad order/site {r['order_id']}/{r['site_id']}")
            continue
        if not _dt(r["timestamp"]) < actual[r["order_id"]]:
            err(f"site_state.csv: row for {r['order_id']} at {r['timestamp']} after the site was ready")
        if r["current_status"] not in ("NOT_READY", "PREPARING", "DELAYED") or r["crew_status"] not in ("READY", "NOT_READY") \
                or r["pump_status"] not in ("NONE", "READY", "DOWN") or r["weather"] not in ("CLEAR", "RAIN"):
            err(f"site_state.csv: bad enum for {r['order_id']} at {r['timestamp']}")
        if not 0 <= int(r["prep_progress_pct"]) <= 90:
            err(f"site_state.csv: prep_progress_pct out of 0-90 for {r['order_id']}")

    trip_ids = {t["trip_id"] for t in tables["orders/trips.csv"]}
    if {r["trip_id"] for r in tables["ground_truth/trip_service.csv"]} != trip_ids:
        err("trip_service.csv: needs exactly one row per trip")
    for r in tables["ground_truth/trip_service.csv"]:
        if float(r["actual_unload_min"]) <= 0:
            err(f"trip_service.csv {r['trip_id']}: non-positive unload time")

    for e in events:
        if e["event_type"] not in EVENT_TYPES:
            err(f"events.json {e['event_id']}: unknown type {e['event_type']}")
        for key, pool in (("site_id", sites), ("order_id", orders), ("vehicle_id", vehicles)):
            if key in e and e[key] not in pool:
                err(f"events.json {e['event_id']}: unknown {key} {e[key]}")
        for s in e.get("site_ids", []):
            if s not in sites:
                err(f"events.json {e['event_id']}: unknown site {s}")

    return problems
