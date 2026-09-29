# traffic_simulator.py -- hourly travel times plant <-> site (skill.md section 7)
"""TravelTime = BaseTravelTime x TrafficMultiplier, one row per directed
plant-site edge per hour. In the simulator this is the travel time trucks
will actually experience; forecasting it is a separate, later question.

multiplier = 1 + (profile[hour] - 1) * traffic_excess_scale
             x edge noise (lognormal) x rain factor x active spikes
"""

import math

from .common import hhmm_to_min, iso_to_min, road_km, rng


def build_travel_profile(world: dict, cfg: dict) -> list:
    """Typical travel time per edge and hour: base x hourly profile, with no
    noise, no scenario scaling, no rain and no spikes. This is what a planner
    knows the day before; it is identical in every scenario."""
    tc = cfg["travel"]
    plant = world["plants"][0]
    p_loc = (plant["latitude"], plant["longitude"])
    h0 = hhmm_to_min(cfg["simulation"]["day_start"]) // 60
    h1 = hhmm_to_min(cfg["simulation"]["day_end"]) // 60
    rows = []
    for s in world["sites"]:
        base = road_km(p_loc, (s["latitude"], s["longitude"]), tc["circuity"]) / tc["free_flow_kmh"] * 60
        for frm, to in ((plant["plant_id"], s["site_id"]), (s["site_id"], plant["plant_id"])):
            for h in range(h0, h1):
                rows.append({"from_node": frm, "to_node": to, "hour": h,
                             "typical_travel_min": round(base * tc["hourly_multiplier"].get(h, 1.0), 2)})
    return rows


def build_traffic(world: dict, cfg: dict, scenario: dict, mags: dict, events: list, seed: int) -> list:
    tc = cfg["travel"]
    plant = world["plants"][0]
    p_loc = (plant["latitude"], plant["longitude"])
    h0 = hhmm_to_min(cfg["simulation"]["day_start"]) // 60
    h1 = hhmm_to_min(cfg["simulation"]["day_end"]) // 60
    rain = mags["rain"]["traffic_factor"] if scenario["weather"] == "RAIN" else 1.0
    spikes = [e for e in events if e["event_type"] == "TRAFFIC_SPIKE"]
    date = cfg["simulation"]["date"]

    rows = []
    for s in world["sites"]:
        km = road_km(p_loc, (s["latitude"], s["longitude"]), tc["circuity"])
        base = km / tc["free_flow_kmh"] * 60
        for frm, to in ((plant["plant_id"], s["site_id"]), (s["site_id"], plant["plant_id"])):
            g = rng(seed, "traffic_noise", frm, to)
            noise = {h: math.exp(g.normal(0, tc["edge_noise_sd"])) for h in range(h0, h1)}
            for h in range(h0, h1):
                profile = tc["hourly_multiplier"].get(h, 1.0)
                mult = (1 + (profile - 1) * scenario["traffic_excess_scale"]) * noise[h] * rain
                for e in spikes:
                    t0 = iso_to_min(e["timestamp"])
                    if s["site_id"] in e["site_ids"] and t0 <= h * 60 < t0 + e["duration_min"]:
                        mult *= 1 + e["extra_multiplier"]
                mult = round(max(0.7, mult), 3)
                rows.append({"from_node": frm, "to_node": to, "timestamp": f"{date}T{h:02d}:00",
                             "road_km": round(km, 3), "base_travel_min": round(base, 2),
                             "traffic_multiplier": mult, "predicted_travel_min": round(base * mult, 2)})
    return rows
