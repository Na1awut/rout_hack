# dispatch_policies.py -- non-AI baselines for Loop 2
"""A policy decides WHEN each truckload is released for loading.

StaticPlanned  (skill.md section 19, system A)
    Fixed the night before from planned data only: release a trip so that,
    with typical traffic, it arrives exactly at its planned arrival time.
    Ignores everything that happens during the day.

ReactiveRule   (a simple dynamic rule with no prediction -- a stand-in for
    system B until the dynamic optimizer exists in Loop 5-6)
    Uses only what a dispatcher knows by now:
      - readiness events already announced shift the order's schedule
      - expected ready = planned + announced shift; once that time has
        passed without the site's "ready" call, the site is assumed ready
        any minute now (no guess of how late)
      - each released load gets a projected unload end from what is known
        (unload start, truck ETA, or live travel time) plus planned unload
        time; the next load targets max(its shifted planned arrival, the
        previous load's projected end)
      - while a truck is already waiting at a site that has not called
        ready, no more trucks are sent to that order
      - departure lead = live travel time of the current hour + load time
"""

import math

READINESS_SHIFT = {"SITE_DELAY": "delay_min", "PUMP_FAILURE": "delay_min", "SITE_READY_LATE": "delay_min"}


def _floor_to(t, step):
    return step * math.floor(t / step)


class StaticPlanned:
    name = "A_static_planned"

    def __init__(self, step_min=5):
        self.step = step_min

    def start(self, plan):
        pid = plan.plant["plant_id"]
        self.release = {}
        for tr in plan.trips:
            arr = tr["planned_arrival_min"]
            guess = arr - plan.typical_travel(pid, tr["site_id"], arr)
            travel = plan.typical_travel(pid, tr["site_id"], int(guess))
            self.release[tr["trip_id"]] = _floor_to(arr - travel - plan.load_min, self.step)
        self.order = sorted(self.release, key=lambda k: (self.release[k], k))

    def decide(self, obs):
        return [k for k in self.order if self.release[k] <= obs.t and not obs.released(k)]


class ReactiveRule:
    name = "R_reactive_rule"

    def start(self, plan):
        self.plan = plan
        self.by_order = {}
        for tr in plan.trips:
            self.by_order.setdefault(tr["order_id"], []).append(tr)
        for trips in self.by_order.values():
            trips.sort(key=lambda x: x["seq"])

    def _shift(self, obs):
        shift = {}
        for e in obs.events():
            if e["event_type"] in READINESS_SHIFT:
                shift[e["order_id"]] = shift.get(e["order_id"], 0) + e[READINESS_SHIFT[e["event_type"]]]
            elif e["event_type"] == "SITE_READY_EARLY":
                shift[e["order_id"]] = shift.get(e["order_id"], 0) - e["early_min"]
        return shift

    def decide(self, obs):
        p = self.plan
        pid = p.plant["plant_id"]
        shift = self._shift(obs)
        t = obs.t
        out = []
        for oid, trips in sorted(self.by_order.items()):
            o = p.orders[oid]
            travel = obs.travel_now(pid, o["site_id"])
            lead = travel + p.load_min
            unload = int(o["estimated_unload_min"])
            s = shift.get(oid, 0)
            ready_called = obs.site_reported_ready(oid)
            er = o["requested_start_min"] + s
            er = min(er, t) if ready_called else max(er, t)
            hold, proj_end = False, None
            for tr in trips:
                tid = tr["trip_id"]
                if obs.released(tid):
                    lg = obs.trip(tid)
                    if "unload_end" in lg:
                        proj_end = lg["unload_end"]
                        continue
                    if "unload_start" in lg:
                        start = lg["unload_start"]
                    else:
                        if "arrive" in lg:
                            arr = lg["arrive"]
                            hold = hold or not ready_called
                        elif "depart" in lg:
                            arr = lg["depart"] + lg["travel_out"]           # truck ETA (GPS)
                        elif "load_start" in lg:
                            arr = lg["load_start"] + p.load_min + travel
                        else:
                            arr = t + lead                                  # released, no truck yet
                        start = max(arr, er, proj_end if proj_end is not None else arr)
                    proj_end = start + unload
                    continue
                if hold:
                    break
                target = tr["planned_arrival_min"] + s
                if proj_end is not None:
                    target = max(target, proj_end)
                if target - lead <= t:
                    out.append(tid)
                break                                           # at most one new load per order per step
        return out
