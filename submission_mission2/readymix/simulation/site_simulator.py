# site_simulator.py -- ground truth: when sites are really ready and how
# long unloading really takes (skill.md sections 6, 8, 10)
"""Produces the labels the AI will later try to predict. Planners and
solvers must never read these files at decision time.

ready_delay_min of an order =
    base delay drawn from the site's hidden reliability trait
  + rain delay (RAIN days)
  + SITE_DELAY / PUMP_FAILURE delay
  SITE_READY_LATE / SITE_READY_EARLY replace the base delay (a surprise
  that contradicts the site's history).
"""

import math

from .common import hhmm_to_min, min_to_iso, rng, round_step
from .world import sample_base_delay


def build_ground_truth(world: dict, cfg: dict, scenario: dict, mags: dict, events: list, seed: int):
    date = cfg["simulation"]["date"]
    traits = {t["site_id"]: t for t in world["site_traits"]}
    on_time = cfg["sites"]["on_time_delay_min"]
    by_order = {}
    for e in events:
        if "order_id" in e:
            by_order.setdefault(e["order_id"], []).append(e)

    orders_gt = []
    for o in world["orders"]:
        oid = o["order_id"]
        base = sample_base_delay(rng(seed, "base_delay", oid), traits[o["site_id"]], on_time)
        causes = ["base_late" if base > on_time["max"] else "on_time"]
        delay = base
        if scenario["weather"] == "RAIN":
            lo, hi = mags["rain"]["extra_delay_min"]
            delay += float(rng(seed, "rain_delay", oid).integers(lo, hi + 1))
            causes.append("rain")
        final_volume = o["total_volume_m3"]
        for e in by_order.get(oid, []):
            et = e["event_type"]
            if et in ("SITE_DELAY", "PUMP_FAILURE"):
                delay += e["delay_min"]
                causes.append(et.lower())
            elif et == "SITE_READY_LATE":
                delay = delay - base + e["delay_min"]
                causes = [c for c in causes if c not in ("base_late", "on_time")] + ["surprise_late"]
            elif et == "SITE_READY_EARLY":
                delay = delay - base - e["early_min"]
                causes = [c for c in causes if c not in ("base_late", "on_time")] + ["surprise_early"]
            elif et == "DEMAND_CHANGE":
                final_volume = max(cfg["orders"]["volume_m3"]["min"],
                                   round_step(final_volume * e["factor"], cfg["orders"]["volume_m3"]["step"]))
        delay = round(delay)
        planned = hhmm_to_min(o["requested_start"][11:])
        orders_gt.append({"order_id": oid, "site_id": o["site_id"],
                          "planned_ready_time": o["requested_start"],
                          "actual_ready_time": min_to_iso(date, planned + delay),
                          "ready_delay_min": delay, "delay_causes": "+".join(causes),
                          "final_volume_m3": final_volume})

    slow = {e["order_id"]: e["factor"] for e in events if e["event_type"] == "SERVICE_SLOWDOWN"}
    orders = {o["order_id"]: o for o in world["orders"]}
    trips_gt = []
    for t in world["trips"]:
        o = orders[t["order_id"]]
        g = rng(seed, "unload", t["trip_id"])
        actual = o["estimated_unload_min"] * math.exp(g.normal(0, cfg["service"]["actual_unload_noise_sd"]))
        actual *= slow.get(t["order_id"], 1.0)
        trips_gt.append({"trip_id": t["trip_id"], "order_id": t["order_id"],
                         "estimated_unload_min": o["estimated_unload_min"],
                         "actual_unload_min": round(actual, 1)})

    site_traits = [{k: t[k] for k in ("site_id", "reliability_class", "p_late", "late_mean_min", "late_sd_min")}
                   for t in world["site_traits"]]
    return orders_gt, trips_gt, site_traits
