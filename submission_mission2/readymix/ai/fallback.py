"""Non-ML fallback using only history, announcements and elapsed time."""
from statistics import NormalDist

import numpy as np

from readymix.simulation.common import iso_to_min


def readiness_revision(events, order_id, t):
    """Observed revisions replace the historical base delay, unlike added delays.

    Mirrors the existing event contract, not ground truth. Other additive
    disruptions remain in announced_delay_min. Never inspect future events.
    """
    return any(e.get("order_id") == order_id
               and e.get("event_type") in ("SITE_READY_LATE", "SITE_READY_EARLY")
               and iso_to_min(e["timestamp"]) <= t for e in events)


def cohort_key(row):
    return (int(float(row["t_rel_min"]) // 30), int(float(row["prep_progress_pct"]) // 30),
            int(row["rain"]), int(row["pump_down"]))


def fit_history(df, min_orders=20):
    """Historical mean by coarse observable state; each order gets one vote.

    This is a fitted baseline, not an untrained rule. Sparse/unseen cohorts
    revert to the announced-delay + site history rule.
    """
    work = df.copy()
    work["cohort"] = [cohort_key(r) for r in work.to_dict("records")]
    per_order = work.groupby(["cohort", "day", "order_id"])["remaining_min"].mean()
    stats = per_order.groupby(level=0).agg(["mean", "count"])
    return {k: float(r["mean"]) for k, r in stats.iterrows() if r["count"] >= min_orders}


def remaining(row, name="rule_hist", history=None):
    elapsed = float(row["t_rel_min"])
    mean = float(row["hist_delay_mean"])
    shift = float(row["announced_delay_min"])
    if name == "event_history":
        # A fresh readiness revision supersedes the site's historical prior.
        # Rain is still uncertain, so use the historical fallback in rain.
        if row.get("readiness_revision", False) and not row["rain"]:
            return max(0.0, shift - elapsed)
        return max(0.0, mean + shift - elapsed)
    if name == "cohort_history":
        return (history or {}).get(cohort_key(row), max(0.0, mean + shift - elapsed))
    if name == "planned":
        return max(0.0, -elapsed)
    if name == "hist":
        return max(0.0, mean - elapsed)
    if name == "rule_hist":
        return max(0.0, mean + shift - elapsed)
    if name != "conditional_history":
        raise ValueError(f"Unknown fallback: {name}")
    # The caller knows the site has NOT reported ready. Condition the historical
    # normal approximation on delay > elapsed; do not predict a past ready time.
    sd = max(1.0, float(row["hist_delay_std"]))
    dist = NormalDist(mean + shift, sd)
    cdf = dist.cdf(elapsed)
    if cdf >= 1 - 1e-12:
        # Stable far-tail residual approximation; avoid inv_cdf(1).
        return sd * sd / max(sd, elapsed - mean - shift)
    return max(0.0, dist.inv_cdf((1 + cdf) / 2) - elapsed)


def predict_rows(df, name, history=None):
    return np.array([remaining(row, name, history) for row in df.to_dict("records")])
