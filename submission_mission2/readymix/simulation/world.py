# world.py -- master data and the day's orders (skill.md sections 2-5)
"""Builds the static world for one simulated day: plant, construction
sites, trucks, orders, and the truckload split of every order.

Hidden site traits (how reliable a site really is) are returned separately
from the tables a planner could see. sites.csv only carries the
historical_delay_mean/std a company would have on file, estimated from
sampled past pours, so it is informative but not the truth.
"""

import math

from .common import hhmm_to_min, min_to_iso, offset_latlon, rng, round_step


def split_trips(volume_m3: float, capacity_m3: float, step_m3: float):
    """Split an order into ceil(V / capacity) truckloads as equal as the
    step allows. With every order > capacity / 2 this keeps every trip
    strictly above capacity / 2, so no two trips can ever share a drum."""
    units = round(volume_m3 / step_m3)
    cap_units = round(capacity_m3 / step_m3)
    n = -(-units // cap_units)
    base, rem = divmod(units, n)
    return [round((base + 1) * step_m3, 4)] * rem + [round(base * step_m3, 4)] * (n - rem)


def _build_sites(cfg, seed, plant, date):
    sc = cfg["sites"]
    n = sc["count"]
    r = rng(seed, "site_classes")
    classes = []
    for name, spec in sc["reliability_mix"].items():
        classes += [name] * round(spec["share"] * n)
    classes = (classes + ["average"] * n)[:n]
    r.shuffle(classes)

    sites, traits = [], []
    r0, r1 = sc["radius_km"]
    for i in range(n):
        sid = f"S{i + 1:03d}"
        g = rng(seed, "site", sid)
        radius = math.sqrt(g.uniform(r0 ** 2, r1 ** 2))
        bearing = g.uniform(0, 2 * math.pi)
        lat, lon = offset_latlon(plant["latitude"], plant["longitude"],
                                 radius * math.cos(bearing), radius * math.sin(bearing))
        trait = dict(site_id=sid, reliability_class=classes[i], **sc["reliability_mix"][classes[i]])
        trait.pop("share")
        hist = [sample_base_delay(g, trait, sc["on_time_delay_min"]) for _ in range(sc["history_pours"])]
        mean = sum(hist) / len(hist)
        sd = math.sqrt(sum((h - mean) ** 2 for h in hist) / (len(hist) - 1))
        sites.append({
            "site_id": sid, "latitude": round(lat, 6), "longitude": round(lon, 6),
            "planned_ready_time": None,                       # filled from its orders
            "site_priority": int(g.integers(1, 6)),
            "pump_available": bool(g.random() < sc["pump_share"]),
            "crew_size": int(g.integers(sc["crew_size"][0], sc["crew_size"][1] + 1)),
            "historical_delay_mean": round(mean, 1),
            "historical_delay_std": round(sd, 1),
        })
        traits.append(trait)
    return sites, traits


def sample_base_delay(g, trait, on_time):
    """Minutes late versus the planned ready time for one pour (negative = early)."""
    if g.random() < trait["p_late"]:
        return max(1.0, g.normal(trait["late_mean_min"], trait["late_sd_min"]))
    return float(min(on_time["max"], max(on_time["min"], g.normal(on_time["mean"], on_time["sd"]))))


def _make_order(g, oid, site, cfg, date, volume_scale):
    oc = cfg["orders"]
    vc = oc["volume_m3"]
    vol = min(vc["max"], max(vc["min"], g.lognormal(vc["lognormal_mean"], vc["lognormal_sd"])))
    vol = round_step(vol * volume_scale, vc["step"])
    lo, hi = (hhmm_to_min(t) for t in oc["requested_start"])
    step = oc["start_step_min"]
    start = lo + step * int(g.integers(0, (hi - lo) // step + 1))
    interval = int(g.integers(oc["target_interval_min"][0], oc["target_interval_min"][1] + 1))
    ur = oc["unload_min_pump"] if site["pump_available"] else oc["unload_min_chute"]
    unload = int(g.integers(ur[0], ur[1] + 1))
    n_trips = len(split_trips(vol, cfg["vehicles"]["capacity_m3"], oc["trip_volume_step_m3"]))
    end = start + (n_trips - 1) * interval + unload + oc["window_slack_min"]
    return {
        "order_id": oid, "site_id": site["site_id"],
        "concrete_type": oc["concrete_types"][int(g.integers(0, len(oc["concrete_types"])))],
        "total_volume_m3": vol, "remaining_volume_m3": vol,
        "requested_start": min_to_iso(date, start), "requested_end": min_to_iso(date, end),
        "target_interval_min": interval, "estimated_unload_min": unload,
        "priority": int(g.integers(oc["priority"][0], oc["priority"][1] + 1)),
        "status": "ACTIVE",
    }


def build_world(cfg: dict, scenario: dict, seed: int, world_seed: int = None) -> dict:
    """world_seed fixes the company (sites, their hidden traits, trucks); seed
    is the day (orders and everything that happens). world_seed = seed by
    default, which is byte-identical to loop01-v1/v2 datasets."""
    world_seed = seed if world_seed is None else world_seed
    date = cfg["simulation"]["date"]
    p = cfg["plant"]
    plant = {k: p[k] for k in ("plant_id", "plant_name", "latitude", "longitude",
                               "loading_bays", "load_time_min", "wash_time_min",
                               "operating_start", "operating_end")}
    sites, traits = _build_sites(cfg, world_seed, plant, date)

    vc = cfg["vehicles"]
    a0, a1 = (hhmm_to_min(t) for t in vc["available_from"])
    vehicles = []
    for i in range(vc["count"]):
        vid = f"T{i + 1:03d}"
        g = rng(world_seed, "vehicle", vid)
        vehicles.append({
            "vehicle_id": vid, "capacity_m3": vc["capacity_m3"], "plant_id": plant["plant_id"],
            "available_from": min_to_iso(date, a0 + 15 * int(g.integers(0, (a1 - a0) // 15 + 1))),
            "current_lat": plant["latitude"], "current_lon": plant["longitude"], "status": "AVAILABLE",
            "fuel_type": vc["fuel_type"],
            "fuel_efficiency_km_l": round(g.uniform(*vc["fuel_efficiency_km_l"]), 2),
            "idle_fuel_l_h": round(g.uniform(*vc["idle_fuel_l_h"]), 2),
            "max_shift_min": vc["max_shift_min"],
        })

    # every site gets at least one order; the rest land anywhere
    n = cfg["orders"]["count"]
    ga = rng(seed, "order_sites")
    site_idx = list(range(len(sites))) + [int(x) for x in ga.integers(0, len(sites), n - len(sites))]
    ga.shuffle(site_idx)
    orders = [_make_order(rng(seed, "order", f"O{k + 1:03d}"), f"O{k + 1:03d}", sites[s], cfg, date,
                          scenario["demand_scale"]) for k, s in enumerate(site_idx)]
    ge = rng(seed, "extra_order_sites")
    for k in range(scenario["extra_orders"]):
        oid = f"O{n + k + 1:03d}"
        orders.append(_make_order(rng(seed, "extra_order", oid), oid, sites[int(ge.integers(0, len(sites)))],
                                  cfg, date, scenario["demand_scale"]))

    for s in sites:
        starts = sorted(o["requested_start"] for o in orders if o["site_id"] == s["site_id"])
        s["planned_ready_time"] = starts[0]

    trips = []
    for o in orders:
        start = hhmm_to_min(o["requested_start"][11:])
        for seq, vol in enumerate(split_trips(o["total_volume_m3"], vc["capacity_m3"],
                                              cfg["orders"]["trip_volume_step_m3"]), 1):
            trips.append({"trip_id": f"{o['order_id']}-{seq:02d}", "order_id": o["order_id"],
                          "site_id": o["site_id"], "seq": seq, "volume_m3": vol,
                          "planned_arrival": min_to_iso(date, start + (seq - 1) * o["target_interval_min"])})

    return {"plants": [plant], "sites": sites, "vehicles": vehicles, "orders": orders,
            "trips": trips, "site_traits": traits}
