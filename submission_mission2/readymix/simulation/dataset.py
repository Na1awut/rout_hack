# dataset.py -- load a generated dataset, split by who may read what
"""Three loaders, one per information class (manifest.json "causality"):

  load_plan(root)     master/* + orders/*: known before the day starts.
                      Planners and policies may hold this.
  load_runtime(root)  realized traffic + events. Only the execution engine
                      holds it; policies see the part up to "now" through
                      an Observation.
  load_truth(root)    ground_truth/*: actual ready times and unload
                      durations. Only the execution engine holds it.

All clock values are integer minutes after midnight.
"""

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from .common import hhmm_to_min, iso_to_min


def _rows(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@dataclass
class Plan:
    name: str
    plant: dict
    sites: dict                 # site_id -> row
    vehicles: list              # rows, with "available_from_min"
    orders: dict                # order_id -> row, with "requested_start_min"
    trips: list                 # rows, with "planned_arrival_min", ordered as in trips.csv
    typical: dict               # (from, to, hour) -> typical travel minutes
    open_min: int = 0
    close_min: int = 0
    load_min: int = 0
    wash_min: int = 0
    bays: int = 1

    def typical_travel(self, frm, to, t_min):
        h = min(max(t_min // 60, self._h0), self._h1)
        return self.typical[(frm, to, h)]

    def __post_init__(self):
        hours = [h for (_, _, h) in self.typical]
        self._h0, self._h1 = min(hours), max(hours)


@dataclass
class Runtime:
    traffic: dict               # (from, to, hour) -> realized travel minutes
    events: list                # with "t" (minutes) added
    site_states: dict = field(default_factory=dict)  # order -> causal reports
    h0: int = field(init=False)
    h1: int = field(init=False)

    def __post_init__(self):
        hours = [h for (_, _, h) in self.traffic]
        self.h0, self.h1 = min(hours), max(hours)

    def travel(self, frm, to, t_min):
        """Realized travel for a departure at t_min (hour slot, clamped to the table)."""
        return self.traffic[(frm, to, min(max(t_min // 60, self.h0), self.h1))]


@dataclass
class Truth:
    ready_min: dict             # order_id -> actual ready minute
    unload_min: dict            # trip_id -> actual unload minutes (float)


def load_plan(root) -> Plan:
    root = Path(root)
    plant = _rows(root / "master/plants.csv")[0]
    vehicles = _rows(root / "master/vehicles.csv")
    for v in vehicles:
        v["available_from_min"] = iso_to_min(v["available_from"])
    orders = {o["order_id"]: o for o in _rows(root / "orders/orders.csv")}
    for o in orders.values():
        o["requested_start_min"] = iso_to_min(o["requested_start"])
    trips = _rows(root / "orders/trips.csv")
    for t in trips:
        t["planned_arrival_min"] = iso_to_min(t["planned_arrival"])
        t["seq"] = int(t["seq"])
    typical = {(r["from_node"], r["to_node"], int(r["hour"])): float(r["typical_travel_min"])
               for r in _rows(root / "master/travel_profile.csv")}
    return Plan(name=root.name, plant=plant, sites={s["site_id"]: s for s in _rows(root / "master/sites.csv")},
                vehicles=vehicles, orders=orders, trips=trips, typical=typical,
                open_min=hhmm_to_min(plant["operating_start"]), close_min=hhmm_to_min(plant["operating_end"]),
                load_min=int(float(plant["load_time_min"])), wash_min=int(float(plant["wash_time_min"])),
                bays=int(plant["loading_bays"]))


def load_runtime(root) -> Runtime:
    root = Path(root)
    traffic = {(r["from_node"], r["to_node"], int(r["timestamp"][11:13])): float(r["predicted_travel_min"])
               for r in _rows(root / "runtime/traffic.csv")}
    events = json.loads((root / "runtime/events.json").read_text(encoding="utf-8"))
    for e in events:
        e["t"] = iso_to_min(e["timestamp"])
    states = {}
    state_path = root / "runtime/site_state.csv"
    if state_path.exists():
        for r in _rows(state_path):
            states.setdefault(r["order_id"], []).append(r)
        for rows in states.values():
            rows.sort(key=lambda r: r["timestamp"])
    return Runtime(traffic=traffic, events=events, site_states=states)


def load_truth(root) -> Truth:
    root = Path(root)
    return Truth(ready_min={r["order_id"]: iso_to_min(r["actual_ready_time"])
                            for r in _rows(root / "ground_truth/order_readiness.csv")},
                 unload_min={r["trip_id"]: float(r["actual_unload_min"])
                             for r in _rows(root / "ground_truth/trip_service.csv")})
