# disruption_generator.py -- scenario events (skill.md section 21)
"""Turns a scenario's event counts into concrete, timestamped events.

`timestamp` is when the event becomes observable to a dispatcher, not
when its effect lands: a SITE_DELAY is announced some time before the
planned ready time it pushes back. Rolling re-optimization (Loop 6)
reacts to events at their timestamp.
"""

from .common import hhmm_to_min, min_to_iso, rng


def _pick(g, items, k):
    if k <= 0 or not items:
        return []
    idx = g.choice(len(items), size=min(k, len(items)), replace=False)
    return [items[int(i)] for i in sorted(idx)]


def generate_events(world: dict, scenario: dict, mags: dict, seed: int, date: str) -> list:
    sites = world["sites"]
    orders = world["orders"]
    traits = {t["site_id"]: t for t in world["site_traits"]}
    events = []
    first_order = {}
    for o in sorted(orders, key=lambda o: (o["requested_start"], o["order_id"])):
        first_order.setdefault(o["site_id"], o)

    def notice(g, planned_iso):
        lo, hi = mags["notice_before_ready_min"]
        return hhmm_to_min(planned_iso[11:]) - int(g.integers(lo, hi + 1))

    def add(t, etype, **kw):
        events.append({"timestamp": min_to_iso(date, t), "event_type": etype, **kw})

    g = rng(seed, "ev_traffic_spike")
    for _ in range(scenario["traffic_spikes"]):
        m = mags["traffic_spike"]
        hit = _pick(g, [s["site_id"] for s in sites], 3)
        add(60 * int(g.integers(7, 17)), "TRAFFIC_SPIKE", site_ids=hit,
            extra_multiplier=round(float(g.uniform(*m["extra"])), 3),
            duration_min=60 * int(g.integers(m["hours"][0], m["hours"][1] + 1)))

    g = rng(seed, "ev_site_delay")
    for sid in _pick(g, [s["site_id"] for s in sites], scenario["site_delays"]):
        o = first_order[sid]
        add(notice(g, o["requested_start"]), "SITE_DELAY", site_id=sid, order_id=o["order_id"],
            delay_min=int(g.integers(mags["site_delay_min"][0], mags["site_delay_min"][1] + 1)))

    g = rng(seed, "ev_pump_failure")
    pumped = [s["site_id"] for s in sites if s["pump_available"]]
    for sid in _pick(g, pumped, scenario["pump_failures"]):
        o = first_order[sid]
        add(notice(g, o["requested_start"]), "PUMP_FAILURE", site_id=sid, order_id=o["order_id"],
            delay_min=int(g.integers(mags["pump_failure_min"][0], mags["pump_failure_min"][1] + 1)))

    g = rng(seed, "ev_truck_breakdown")
    for v in _pick(g, [v["vehicle_id"] for v in world["vehicles"]], scenario["truck_breakdowns"]):
        add(hhmm_to_min("09:00") + 15 * int(g.integers(0, 17)), "TRUCK_BREAKDOWN", vehicle_id=v)

    g = rng(seed, "ev_service_slowdown")
    for o in _pick(g, orders, scenario["service_slowdowns"]):
        add(hhmm_to_min(o["requested_start"][11:]), "SERVICE_SLOWDOWN", site_id=o["site_id"],
            order_id=o["order_id"],
            factor=round(float(g.uniform(*mags["service_slowdown_factor"])), 3))

    g = rng(seed, "ev_demand_change")
    for o in _pick(g, orders, scenario["demand_changes"]):
        add(hhmm_to_min(o["requested_start"][11:]) - 60, "DEMAND_CHANGE", site_id=o["site_id"],
            order_id=o["order_id"],
            factor=round(float(g.uniform(*mags["demand_change_factor"])), 3))

    g = rng(seed, "ev_surprise_late")
    good = [sid for sid, t in traits.items() if t["reliability_class"] == "good"]
    for sid in _pick(g, good, scenario["surprise_late_reliable"]):
        o = first_order[sid]
        add(notice(g, o["requested_start"]), "SITE_READY_LATE", site_id=sid, order_id=o["order_id"],
            delay_min=int(g.integers(mags["surprise_late_min"][0], mags["surprise_late_min"][1] + 1)))

    g = rng(seed, "ev_surprise_early")
    poor = [sid for sid, t in traits.items() if t["reliability_class"] == "poor"]
    for sid in _pick(g, poor, scenario["surprise_early_poor"]):
        o = first_order[sid]
        add(notice(g, o["requested_start"]), "SITE_READY_EARLY", site_id=sid, order_id=o["order_id"],
            early_min=int(g.integers(mags["surprise_early_min"][0], mags["surprise_early_min"][1] + 1)))

    events.sort(key=lambda e: (e["timestamp"], e["event_type"]))
    for i, e in enumerate(events, 1):
        e["event_id"] = f"E{i:03d}"
    return [{"event_id": e.pop("event_id"), **e} for e in events]
