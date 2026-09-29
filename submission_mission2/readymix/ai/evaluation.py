# evaluation.py -- baselines and metrics for the readiness models (skill.md section 11)
"""Every predictor outputs remaining_min (minutes from t until the site is
ready) and is clipped at 0, because the site has not called ready yet.

Non-ML baselines (all get the same clipping):
  planned       ready at the planned time
  hist          planned + the site's historical mean delay
  rule          planned + delays already announced by events (what Loop 2's R uses)
  rule_hist     planned + announced + historical mean
The best baseline is chosen on the validation days, never on test.
"""

import math

import numpy as np

BASELINES = ["planned", "hist", "rule", "rule_hist"]


def baseline_remaining(df, name):
    P, t = df["planned"].to_numpy(float), df["t"].to_numpy(float)
    shift = {"planned": 0.0, "hist": df["hist_delay_mean"].to_numpy(float),
             "rule": df["announced_delay_min"].to_numpy(float),
             "rule_hist": df["announced_delay_min"].to_numpy(float) + df["hist_delay_mean"].to_numpy(float)}[name]
    return np.maximum(0.0, P + shift - t)


def baseline_late_prob(df, threshold=15):
    """P(delay > threshold): 1 once the site is already that late; else a normal
    approximation around planned + announced + historical mean."""
    mu = df["hist_delay_mean"].to_numpy(float) + df["announced_delay_min"].to_numpy(float)
    sd = np.maximum(1.0, df["hist_delay_std"].to_numpy(float))
    z = (threshold - mu) / sd
    p = 1 - 0.5 * (1 + np.vectorize(math.erf)(z / math.sqrt(2)))
    return np.where(df["delay_so_far_min"].to_numpy(float) > threshold, 1.0, p)


def mae(y, p):
    return float(np.mean(np.abs(np.asarray(y, float) - np.asarray(p, float))))


def at_lead(df, lead):
    return df[df["t"] == df["planned"] - lead]


def paired_bootstrap(df, err_a, err_b, resamples, seed):
    """95% CI of MAE(a) - MAE(b), resampling whole orders (rows of one order stay together)."""
    key = df["day"].astype(str) + "/" + df["order_id"].astype(str)
    g = (np.abs(err_a) - np.abs(err_b))
    frame = {"k": key.to_numpy(), "d": g}
    import pandas as pd
    agg = pd.DataFrame(frame).groupby("k")["d"].agg(["sum", "count"])
    s, c = agg["sum"].to_numpy(), agg["count"].to_numpy()
    r = np.random.default_rng(seed)
    idx = r.integers(0, len(s), size=(resamples, len(s)))
    stats = s[idx].sum(1) / c[idx].sum(1)
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)), float(s.sum() / c.sum())


def brier(y, p):
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def ece(y, p, bins=10):
    y, p = np.asarray(y, float), np.asarray(p, float)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for i in range(bins):
        m = (p >= edges[i]) & ((p < edges[i + 1]) if i < bins - 1 else (p <= 1))
        if m.any():
            total += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(total)


def auc(y, p):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, p)) if len(set(np.asarray(y).tolist())) > 1 else math.nan


def f1_at(y, p, thr=0.5):
    from sklearn.metrics import f1_score, precision_score, recall_score
    yh = (np.asarray(p) >= thr).astype(int)
    return (float(precision_score(y, yh, zero_division=0)), float(recall_score(y, yh, zero_division=0)),
            float(f1_score(y, yh, zero_division=0)))
