# common.py -- seeded randomness, clock and geometry shared by the simulator
"""Every random draw comes from a stream keyed by (seed, purpose, entity).
Adding an event or a scenario therefore never shifts the draws of any other
entity: the same seed gives the same base world in every scenario.
"""

import hashlib
import math
from datetime import datetime, timedelta

import numpy as np

KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LON_EQUATOR = 111.320


def rng(seed: int, *keys) -> np.random.Generator:
    digest = hashlib.sha256("|".join(str(k) for k in keys).encode()).digest()
    return np.random.default_rng([seed, int.from_bytes(digest[:8], "little")])


# -- clock: the simulator works in integer minutes after midnight ---------

def hhmm_to_min(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def min_to_hhmm(t: int) -> str:
    return f"{t // 60:02d}:{t % 60:02d}"


def min_to_iso(date: str, t: int) -> str:
    return (datetime.fromisoformat(date) + timedelta(minutes=int(t))).strftime("%Y-%m-%dT%H:%M")


def iso_to_min(s: str) -> int:
    d = datetime.fromisoformat(s)
    return d.hour * 60 + d.minute


# -- geometry: local planar approximation around the plant ---------------

def planar_km(lat0: float, lon0: float, lat: float, lon: float):
    """(x, y) km east/north of (lat0, lon0). Good to well under 1 % at < 50 km."""
    return ((lon - lon0) * KM_PER_DEG_LON_EQUATOR * math.cos(math.radians(lat0)),
            (lat - lat0) * KM_PER_DEG_LAT)


def offset_latlon(lat0: float, lon0: float, x_km: float, y_km: float):
    return (lat0 + y_km / KM_PER_DEG_LAT,
            lon0 + x_km / (KM_PER_DEG_LON_EQUATOR * math.cos(math.radians(lat0))))


def road_km(origin, dest, circuity: float) -> float:
    """Road-distance proxy = straight-line planar km x circuity. The same
    function feeds the traffic table and the solver projection, so both see
    the same geometry."""
    x, y = planar_km(origin[0], origin[1], dest[0], dest[1])
    return math.hypot(x, y) * circuity


def round_step(x: float, step: float) -> float:
    return round(round(x / step) * step, 4)
