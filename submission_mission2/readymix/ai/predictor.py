# predictor.py -- the AI Output Contract (skill.md sections 12 and 31)
"""SiteReadyPredictor.predict(...) returns exactly one JSON-able dict per
site/order at time t. The optimization layer accepts this format only.

  {site_id, order_id, prediction_time, predicted_ready_time, ready_delay_min,
   interval_min: [lo, hi], predicted_service_min, delay_probability,
   confidence, model_version, fallback_used, fallback_reason}

Fallback (section 31): malformed runtime input, model error, inputs outside
training range or confidence < threshold. Version 3 also respects observed
dry-weather readiness revisions, which replace the historical base delay.
The rule uses only information already announced and states its reason.
Invalid runtime features and model failures fall back. Identity, planned
time, service estimate and clock are required: invalid values raise ValueError
because a dispatchable result cannot be constructed without inventing them.
"""

from datetime import datetime, timedelta
import math
from pathlib import Path

import joblib
import numpy as np

from .calibration import out_of_range
from .features import FEATURES, feature_row
from .fallback import remaining as rule_remaining, readiness_revision

MODEL_DIR = Path(__file__).resolve().parent / "models"
REQUIRED = {"site_id": str, "order_id": str, "prediction_time": str, "predicted_ready_time": str,
            "ready_delay_min": int, "interval_min": list, "predicted_service_min": (int, float),
            "delay_probability": float, "confidence": float, "model_version": str,
            "fallback_used": bool, "fallback_reason": (str, type(None))}


def fallback_remaining(f, t, planned):
    return max(0.0, planned + f["announced_delay_min"] + f["hist_delay_mean"] - t)


class SiteReadyPredictor:
    def __init__(self, bundle="site_ready_v3.joblib", threshold=None):
        b = joblib.load(MODEL_DIR / bundle)
        self.b = b
        self.version = b["version"]
        self.threshold = b["confidence_threshold"] if threshold is None else threshold

    def predict(self, state, site, order, events, t, date):
        try:
            planned = _minute(order["requested_start"])
            service = float(order["estimated_unload_min"])
            if not site["site_id"] or not order["order_id"] or not math.isfinite(service) or service <= 0:
                raise ValueError("invalid identity or service estimate")
            if not math.isfinite(t) or int(t) != t or not 0 <= t < 1440:
                raise ValueError("clock must be integer minutes within the simulation day")
            _iso(date, t)
        except (KeyError, TypeError, ValueError, OverflowError) as e:
            raise ValueError("valid site/order identity, schedule, service estimate and clock required") from e
        reason = None
        try:
            f = feature_row(state, site, order, events, t)
            if not all(math.isfinite(float(v)) for v in f.values()):
                raise ValueError("nonfinite feature")
            if _minute(state["timestamp"]) > t:
                raise ValueError("future state")
        except Exception as e:                                   # malformed input
            f, reason = None, f"bad input: {type(e).__name__}"
        conf, prob, lo, hi = 0.0, None, None, None
        if f is not None:
            f["readiness_revision"] = readiness_revision(events, order["order_id"], t)
            bad = out_of_range(f, self.b["feature_ranges"])
            if self.b.get("fallback_on_revision", False) and f["readiness_revision"] and not f["rain"]:
                reason = "announced readiness revision supersedes historical prior"
            elif bad and self.b.get("fallback_on_out_of_range", True):
                reason = "out of training range: " + ",".join(bad)
            else:
                try:
                    X = np.array([[f[k] for k in FEATURES]], float)
                    rem = float(self.b["regressor"].predict(X)[0])
                    qlo, qhi = self.b["q_lo"].predict(X)[0], self.b["q_hi"].predict(X)[0]
                    m = self.b["conformal_margin"]
                    lo, hi = max(0.0, min(qlo, qhi) - m), max(0.0, max(qlo, qhi) + m)
                    conf = float(self.b["confidence_model"].predict([hi - lo])[0])
                    prob = float(self.b["classifier"].predict_proba(X)[0, 1])
                    if not all(math.isfinite(float(v)) for v in (rem, qlo, qhi, m, conf, prob)):
                        raise ValueError("nonfinite model output")
                    if not 0 <= conf <= 1 or not 0 <= prob <= 1:
                        raise ValueError("invalid model probability")
                    rem = max(0.0, rem)
                    if f["delay_so_far_min"] > 15:
                        prob = 1.0
                    if conf < self.threshold:
                        reason = f"low confidence {conf:.2f} < {self.threshold}"
                except Exception as e:
                    reason = f"model error: {type(e).__name__}"
        if reason is not None:
            if f is None:
                rem = max(0.0, planned - t)
                lo = hi = rem
            else:
                rem = rule_remaining(f, self.b.get("fallback", "rule_hist"), self.b.get("fallback_history"))
            # An AI interval/confidence does not describe the substituted rule.
            # Zero confidence marks this as an uncalibrated fallback estimate.
            conf = 0.0
            lo = hi = rem
            prob = 1.0 if (f and f["delay_so_far_min"] > 15) else 0.5
        ready = t + round(rem)
        return {
            "site_id": str(site["site_id"]), "order_id": str(order["order_id"]),
            "prediction_time": _iso(date, t), "predicted_ready_time": _iso(date, ready),
            "ready_delay_min": int(ready - planned), "interval_min": [round(float(lo), 1), round(float(hi), 1)],
            "predicted_service_min": service,
            "delay_probability": round(float(prob), 4), "confidence": round(float(conf), 4),
            "model_version": self.version, "fallback_used": reason is not None, "fallback_reason": reason,
        }


def validate_prediction(p) -> list:
    if not isinstance(p, dict):
        return ["prediction must be a dict"]
    errs = [f"missing {k}" for k in REQUIRED if k not in p]
    errs += [f"extra {k}" for k in p if k not in REQUIRED]
    for k, typ in REQUIRED.items():
        if k in p and (not isinstance(p[k], typ) or
                       (isinstance(p[k], bool) and typ is not bool)):
            errs.append(f"{k} has type {type(p[k]).__name__}")
    if not errs:
        if not 0 <= p["delay_probability"] <= 1 or not 0 <= p["confidence"] <= 1:
            errs.append("probability/confidence outside [0, 1]")
        bounds = p["interval_min"]
        finite = lambda v: type(v) in (int, float) and math.isfinite(v)
        if (len(bounds) != 2 or not all(finite(v) for v in bounds)
                or not 0 <= bounds[0] <= bounds[1]):
            errs.append("interval_min must be finite [lo, hi] with 0 <= lo <= hi")
        if not finite(p["predicted_service_min"]) or p["predicted_service_min"] <= 0:
            errs.append("predicted_service_min must be finite and positive")
        try:
            if datetime.fromisoformat(p["predicted_ready_time"]) < datetime.fromisoformat(p["prediction_time"]):
                errs.append("predicted_ready_time before prediction_time (site has not called ready)")
        except (ValueError, TypeError):
            errs.append("prediction timestamps must be valid ISO dates with compatible timezones")
        if p["fallback_used"] and not p["fallback_reason"]:
            errs.append("fallback_used requires a reason")
        if not p["fallback_used"] and p["fallback_reason"] is not None:
            errs.append("fallback_reason must be null when fallback is not used")
    return errs


def _minute(iso):
    d = datetime.fromisoformat(iso)
    return d.hour * 60 + d.minute


def _iso(date, t):
    return (datetime.fromisoformat(date) + timedelta(minutes=int(t))).strftime("%Y-%m-%dT%H:%M:%S")
