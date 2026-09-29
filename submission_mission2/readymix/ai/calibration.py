# calibration.py -- Loop 4: how far to trust a readiness prediction
"""Three pieces, all fit on train (models) and validation (calibration),
never on test:

1. Prediction interval: quantile gradient boosting at q_lo / q_hi, widened
   by split-conformal calibration on validation (CQR, Romano et al. 2019)
   so that ~80 % of true ready times fall inside.
2. confidence = P(|point error| <= tolerance) estimated from the interval
   width with isotonic regression on validation. This is the number the
   AI Output Contract (skill.md section 12) calls `confidence`.
3. Guard: a row whose features fall outside what training ever saw is
   out-of-distribution; the predictor must not trust it (section 31).
"""

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.isotonic import IsotonicRegression

from .features import FEATURES


def fit_quantiles(cfg, df, q_lo=0.1, q_hi=0.9, features=FEATURES):
    gb = cfg["models"]["gradient_boosting"]
    out = {}
    for name, q in (("lo", q_lo), ("hi", q_hi)):
        m = HistGradientBoostingRegressor(random_state=cfg["model_seed"], loss="quantile", quantile=q, **gb)
        m.fit(df[features].to_numpy(float), df["remaining_min"].to_numpy(float))
        out[name] = m
    return out


def raw_interval(qm, df, features=FEATURES):
    X = df[features].to_numpy(float)
    lo, hi = qm["lo"].predict(X), qm["hi"].predict(X)
    return np.minimum(lo, hi), np.maximum(lo, hi)


def conformal_margin(qm, val, coverage=0.8, features=FEATURES):
    lo, hi = raw_interval(qm, val, features)
    y = val["remaining_min"].to_numpy(float)
    score = np.maximum(lo - y, y - hi)
    n = len(score)
    k = min(n - 1, int(np.ceil((n + 1) * coverage)) - 1)
    return float(np.sort(score)[k])


def interval(qm, margin, df, features=FEATURES):
    lo, hi = raw_interval(qm, df, features)
    return np.maximum(0.0, lo - margin), np.maximum(0.0, hi + margin)


def fit_confidence(width, abs_err, tolerance):
    iso = IsotonicRegression(increasing=False, out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(np.asarray(width, float), (np.asarray(abs_err, float) <= tolerance).astype(float))
    return iso


def feature_ranges(df, features=FEATURES):
    return {f: (float(df[f].min()), float(df[f].max())) for f in features}


def out_of_range(row: dict, ranges: dict):
    """Names of features outside the training range (empty list = in range)."""
    bad = []
    for f, (lo, hi) in ranges.items():
        v = row.get(f)
        if v is None or (isinstance(v, float) and np.isnan(v)) or not lo <= float(v) <= hi:
            bad.append(f)
    return bad
