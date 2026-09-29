# executor.py -- play one day minute by minute under a dispatch policy
"""The engine owns the truth (actual ready times, unload durations, realized
traffic). A policy only decides WHEN each truckload is released for
loading; it sees the world through an Observation that holds nothing from
the future. Which truck takes a released trip is fixed and simple: the
truck that has been idle at the plant the longest (all trucks are
identical and start from the same plant in V1).

Per minute t, in this order:
  1. events that become true at t (TRUCK_BREAKDOWN)
  2. trucks whose current activity ends at t move on
       LOADING -> TRAVEL_OUT -> WAIT_SITE -> UNLOADING -> TRAVEL_BACK -> WASH -> IDLE
  3. each order's discharge point starts the next queued truck (first come,
     first served) once the site is really ready
  4. every `step_min`, the policy may release trips
  5. released trips start loading while a truck and a loading bay are free
     and the plant is open

Modelling rules (ASSUMED, stated so later loops can revisit them):
  - travel time = realized slot value at the departure minute, rounded to
    whole minutes (>= 1); hours past the traffic table use its last slot
  - one truck discharges at a time per order; trucks queue on arrival
  - a breakdown takes the truck out when it is next back at the plant
    (it finishes the load it is carrying)
  - no load starts outside plant hours; trips never loaded are unserved
"""

import time
from .common import iso_to_min

from .dataset import load_plan, load_runtime, load_truth

DAY_END = 24 * 60 - 1


class Observation:
    """What a dispatcher knows at minute t. Nothing here is from the future."""

    def __init__(self, t, plan, engine):
        self.t = t
        self.plan = plan
        self._engine = engine

    def events(self):
        return [e for e in self._engine.runtime.events if e["t"] <= self.t]

    def travel_now(self, frm, to):
        """Current hour's realized travel time -- what a live traffic feed shows now."""
        return self._engine.runtime.travel(frm, to, self.t)

    def trip(self, trip_id):
        """Timestamps that have already happened for a trip (missing = not yet)."""
        return dict(self._engine.log[trip_id])

    def site_reported_ready(self, order_id):
        """The site calls the plant when it is ready: known from that minute on."""
        return self._engine.truth.ready_min[order_id] <= self.t

    def released(self, trip_id):
        return "released" in self._engine.log[trip_id]

    def site_state(self, order_id):
        """Latest report received by now; copies cannot mutate engine state."""
        rows = self._engine.runtime.site_states.get(order_id, [])
        for row in reversed(rows):
            if iso_to_min(row["timestamp"]) <= self.t:
                return dict(row)
        return None

    def loading_slots(self):
        """Capacity available NOW, after committed loads and breakdowns."""
        trucks = self._engine.trucks
        return max(0, min(sum(x["state"] == "IDLE" for x in trucks.values()),
                          self.plan.bays - sum(x["state"] == "LOADING" for x in trucks.values())))


class Engine:
    def __init__(self, root, policy, step_min=5):
        self.plan = load_plan(root)
        self.runtime = load_runtime(root)
        self.truth = load_truth(root)
        self.policy = policy
        self.step = step_min
        self.log = {t["trip_id"]: {} for t in self.plan.trips}
        self.trip = {t["trip_id"]: t for t in self.plan.trips}

    def run(self):
        p = self.plan
        pid = p.plant["plant_id"]
        trucks = {v["vehicle_id"]: {"state": "OFF", "until": None, "trip": None, "idle_since": None,
                                    "avail": v["available_from_min"], "pending_break": False}
                  for v in p.vehicles}
        self.trucks = trucks
        queue = {oid: [] for oid in p.orders}
        unloading = {oid: None for oid in p.orders}
        release_q = []
        policy_s = 0.0
        t0 = min(p.open_min, min(v["available_from_min"] for v in p.vehicles)) - 60
        t0 -= t0 % self.step
        breaks = {}
        for e in self.runtime.events:
            if e["event_type"] == "TRUCK_BREAKDOWN":
                breaks.setdefault(e["t"], []).append(e["vehicle_id"])

        self.policy.start(p)
        for t in range(t0, DAY_END + 1):
            for vid in breaks.get(t, []):
                tr = trucks[vid]
                tr["pending_break"] = True
                tr["break_at"] = t
                if tr["state"] in ("OFF", "IDLE"):
                    tr["state"] = "BROKEN"

            for vid in sorted(trucks):
                tr = trucks[vid]
                if tr["state"] == "OFF" and t >= tr["avail"]:
                    tr["state"], tr["idle_since"] = "IDLE", t
                if tr["until"] != t:
                    continue
                tid = tr["trip"]
                lg, trip = self.log[tid], self.trip[tid]
                if tr["state"] == "LOADING":
                    lg["depart"] = t
                    lg["travel_out"] = max(1, round(self.runtime.travel(pid, trip["site_id"], t)))
                    tr["state"], tr["until"] = "TRAVEL_OUT", t + lg["travel_out"]
                elif tr["state"] == "TRAVEL_OUT":
                    lg["arrive"] = t
                    queue[trip["order_id"]].append(vid)
                    tr["state"], tr["until"] = "WAIT_SITE", None
                elif tr["state"] == "UNLOADING":
                    lg["unload_end"] = t
                    unloading[trip["order_id"]] = None
                    lg["travel_back"] = max(1, round(self.runtime.travel(trip["site_id"], pid, t)))
                    tr["state"], tr["until"] = "TRAVEL_BACK", t + lg["travel_back"]
                elif tr["state"] == "TRAVEL_BACK":
                    lg["back"] = t
                    tr["state"], tr["until"] = "WASH", t + p.wash_min
                elif tr["state"] == "WASH":
                    lg["free"] = t
                    tr["trip"], tr["until"] = None, None
                    tr["state"] = "BROKEN" if tr["pending_break"] else "IDLE"
                    tr["idle_since"] = t

            for oid in sorted(queue):
                if unloading[oid] is None and queue[oid] and t >= self.truth.ready_min[oid]:
                    vid = queue[oid].pop(0)
                    tr = trucks[vid]
                    lg = self.log[tr["trip"]]
                    lg["unload_start"] = t
                    lg["unload_dur"] = max(1, round(self.truth.unload_min[tr["trip"]]))
                    unloading[oid] = vid
                    tr["state"], tr["until"] = "UNLOADING", t + lg["unload_dur"]

            if (t - t0) % self.step == 0:
                c = time.perf_counter()
                for tid in self.policy.decide(Observation(t, p, self)):
                    if "released" not in self.log[tid]:
                        self.log[tid]["released"] = t
                        release_q.append(tid)
                policy_s += time.perf_counter() - c

            if p.open_min <= t < p.close_min:
                while release_q and sum(tr["state"] == "LOADING" for tr in trucks.values()) < p.bays:
                    idle = sorted((tr["idle_since"], vid) for vid, tr in trucks.items() if tr["state"] == "IDLE")
                    if not idle:
                        break
                    vid = idle[0][1]
                    tid = release_q.pop(0)
                    tr = trucks[vid]
                    self.log[tid].update(load_start=t, truck=vid)
                    tr["state"], tr["until"], tr["trip"] = "LOADING", t + p.load_min, tid

            if t >= p.close_min and all(tr["state"] in ("OFF", "IDLE", "BROKEN") for tr in trucks.values()):
                break

        return {"plan": p, "log": self.log, "policy_runtime_ms": round(policy_s * 1000, 1),
                "breakdowns": {vid: tr.get("break_at") for vid, tr in trucks.items() if tr["pending_break"]},
                "end_minute": t}


def run_day(root, policy, step_min=5):
    return Engine(root, policy, step_min).run()
