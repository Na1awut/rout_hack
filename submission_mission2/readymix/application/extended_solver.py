"""Deterministic dispatch optimization for single-plant, single-site loads.

Routes and distances are fixed in V1. Optimize release timing and which
orders receive the currently available loading slots. Identical trucks are
assigned longest-idle-first by the executor. No claim of global VRP optimality.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class DispatchJob:
    trip_id: str
    target_min: float
    lead_min: float
    priority: int = 1


def best_release(job, now, close, step, waiting_weight=1, late_weight=1):
    """Exact minimizer on the time grid for one job's early/late arrival cost."""
    if step <= 0 or waiting_weight <= 0 or late_weight <= 0:
        raise ValueError("positive step and objective weights required")
    first = math.ceil(now / step) * step
    if first >= close:
        return None
    desired = job.target_min - job.lead_min
    last = first + ((close - 1 - first) // step) * step
    candidates = {first, last}
    for k in (math.floor(desired / step) * step, math.ceil(desired / step) * step):
        candidates.add(min(last, max(first, k)))
    def cost(release):
        delta = release + job.lead_min - job.target_min
        return waiting_weight * max(0, -delta) + late_weight * max(0, delta)
    release = min(candidates, key=lambda r: (cost(r), r))
    return release, cost(release)


def solve_dispatch(jobs, now, close, slots, step=5, waiting_weight=1, late_weight=1):
    """Select due jobs by delay avoided per available slot, then stable ID.

    Capacity is enforced at commitment time. Remaining jobs stay uncommitted
    and can be re-planned. Released trips never re-enter the candidate list.
    """
    due, plans = [], []
    for job in jobs:
        result = best_release(job, now, close, step, waiting_weight, late_weight)
        if result is None:
            continue
        release, cost = result
        plans.append(dict(trip_id=job.trip_id, release=release, target=job.target_min, cost=cost))
        if release <= now:
            delay = max(0, now + job.lead_min - job.target_min)
            due.append((-delay * max(1, job.priority), job.target_min, job.trip_id))
    chosen = [x[2] for x in sorted(due)[:max(0, slots)]]
    return chosen, plans
