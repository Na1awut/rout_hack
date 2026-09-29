# features.py -- one feature row per (order, observation time) (skill.md section 9)
"""feature_row() takes only things known at time t: the site_state row at t,
master data, the order, and the events already announced. It never sees a
label. Training (from simulated days) and live prediction (Loop 5-6) call
the same function, so what the model learns is what it gets at run time.

Label (added separately by records_from_day):
    remaining_min = actual ready - t   (always > 0: rows exist only before ready)
    ready_delay_min = actual ready - planned
    late15 = ready_delay_min > 15
"""

from readymix.simulation.common import iso_to_min
from .fallback import readiness_revision

READINESS_EVENTS = {"SITE_DELAY": 1, "PUMP_FAILURE": 1, "SITE_READY_LATE": 1, "SITE_READY_EARLY": -1}
CONCRETE = {"M25": 0, "M30": 1, "M35": 2, "M40": 3}
STATUS = {"NOT_READY": 0, "PREPARING": 1, "DELAYED": 2}

FEATURES = ["t_rel_min", "planned_hour", "site_code", "hist_delay_mean", "hist_delay_std", "pump_available",
            "crew_size", "site_priority", "order_volume_m3", "concrete_code", "order_priority",
            "crew_ready", "prep_progress_pct", "minutes_since_report", "pump_down", "status_code",
            "delay_so_far_min", "rain", "announced_delay_min", "has_announcement"]


def announced_shift(events, order_id, t):
    """Sum of readiness shifts announced for this order by time t (early = negative)."""
    s, n = 0, 0
    for e in events:
        if e.get("order_id") == order_id and e["event_type"] in READINESS_EVENTS and iso_to_min(e["timestamp"]) <= t:
            s += e["delay_min"] if READINESS_EVENTS[e["event_type"]] > 0 else -e["early_min"]
            n += 1
    return s, n


def feature_row(state, site, order, events, t):
    """state: the site_state row at t; site: sites.csv row; order: orders.csv row."""
    P = iso_to_min(order["requested_start"])
    shift, n = announced_shift(events, order["order_id"], t)
    since = state["minutes_since_report"]
    return {
        "t_rel_min": t - P,
        "planned_hour": P / 60,
        "site_code": int(site["site_id"][1:]),
        "hist_delay_mean": float(site["historical_delay_mean"]),
        "hist_delay_std": float(site["historical_delay_std"]),
        "pump_available": int(str(site["pump_available"]).lower() == "true"),
        "crew_size": int(site["crew_size"]),
        "site_priority": int(site["site_priority"]),
        "order_volume_m3": float(order["total_volume_m3"]),
        "concrete_code": CONCRETE[order["concrete_type"]],
        "order_priority": int(order["priority"]),
        "crew_ready": int(state["crew_status"] == "READY"),
        "prep_progress_pct": int(state["prep_progress_pct"]),
        "minutes_since_report": -1 if since in ("", None) else int(since),
        "pump_down": int(state["pump_status"] == "DOWN"),
        "status_code": STATUS[state["current_status"]],
        "delay_so_far_min": int(state["delay_so_far_min"]),
        "rain": int(state["weather"] == "RAIN"),
        "announced_delay_min": shift,
        "has_announcement": int(n > 0),
    }


def records_from_day(tables, day_seed, scenario):
    """Feature rows + labels for every site_state row of one simulated day."""
    sites = {s["site_id"]: s for s in tables["master/sites.csv"]}
    orders = {o["order_id"]: o for o in tables["orders/orders.csv"]}
    events = tables["runtime/events.json"]
    ready = {r["order_id"]: iso_to_min(r["actual_ready_time"]) for r in tables["ground_truth/order_readiness.csv"]}
    out = []
    for st in tables["runtime/site_state.csv"]:
        o = orders[st["order_id"]]
        t = iso_to_min(st["timestamp"])
        f = feature_row(st, sites[st["site_id"]], o, events, t)
        P = iso_to_min(o["requested_start"])
        A = ready[o["order_id"]]
        out.append({"day": day_seed, "scenario": scenario, "order_id": o["order_id"], "t": t, "planned": P,
                    "readiness_revision": readiness_revision(events, o["order_id"], t),
                    **f, "remaining_min": A - t, "ready_delay_min": A - P, "late15": int(A - P > 15)})
    return out


def service_records_from_day(tables, day_seed, scenario, decision_lead_min=45):
    """One row per truckload for Target B (unload duration). Decision time =
    planned arrival - decision_lead_min. No execution completion timestamps
    are available here, so previous actual unload is unavailable (-1).
    Ground truth is used only as the target, never as an input feature."""
    sites = {s["site_id"]: s for s in tables["master/sites.csv"]}
    orders = {o["order_id"]: o for o in tables["orders/orders.csv"]}
    unload = {r["trip_id"]: float(r["actual_unload_min"]) for r in tables["ground_truth/trip_service.csv"]}
    slow = {e["order_id"]: iso_to_min(e["timestamp"]) for e in tables["runtime/events.json"]
            if e["event_type"] == "SERVICE_SLOWDOWN"}
    out = []
    for tr in tables["orders/trips.csv"]:
        o, s = orders[tr["order_id"]], sites[tr["site_id"]]
        k = int(tr["seq"])
        decide = iso_to_min(tr["planned_arrival"]) - decision_lead_min
        out.append({"day": day_seed, "scenario": scenario, "trip_id": tr["trip_id"],
                    "estimated_unload_min": float(o["estimated_unload_min"]),
                    "pump_available": int(str(s["pump_available"]).lower() == "true"),
                    "concrete_code": CONCRETE[o["concrete_type"]], "trip_volume_m3": float(tr["volume_m3"]),
                    "crew_size": int(s["crew_size"]), "seq": k, "site_code": int(s["site_id"][1:]),
                    "slowdown_visible": int(tr["order_id"] in slow and slow[tr["order_id"]] <= decide),
                    "prev_actual_unload": -1.0,
                    "actual_unload_min": unload[tr["trip_id"]]})
    return out


SERVICE_FEATURES = ["estimated_unload_min", "pump_available", "concrete_code", "trip_volume_m3", "crew_size",
                    "seq", "site_code", "slowdown_visible", "prev_actual_unload"]
