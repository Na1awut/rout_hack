"""Check candidate runtime contract and batch/runtime parity on fresh days."""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from readymix.ai.predictor import SiteReadyPredictor, validate_prediction
from readymix.ai.features import feature_row, FEATURES
from readymix.ai.fallback import remaining, readiness_revision
from readymix.ai.training_data import load_ai_config, day_scenario
from readymix.ai.calibration import out_of_range
from readymix.simulation.build_dataset import load_configs, simulate
from readymix.simulation.common import iso_to_min


class CachedEstimator:
    """Evaluate the real estimator on every day's row in one batch.

    Only numerical inference is cached: every row still traverses the real
    predictor's validation, revision, OOD, confidence and fallback branches.
    Two rows/day additionally compare against fully uncached runtime calls.
    """
    def __init__(self, estimator, X, proba=False):
        self.proba = proba
        values = estimator.predict_proba(X) if proba else estimator.predict(X)
        self.values = {tuple(x): y for x, y in zip(X, values)}

    def predict(self, X):
        return np.array([self.values[tuple(x)] for x in X])

    predict_proba = predict


def main():
    predictor = SiteReadyPredictor(HERE / "iteration_05/candidate.joblib")
    cfg, scenarios = load_configs()
    checked, fallbacks = 0, 0
    original_models = {k: predictor.b[k] for k in ("regressor", "q_lo", "q_hi", "classifier")}
    ai_cfg = load_ai_config()
    lc = json.loads((HERE / "iteration_05/config.json").read_text())
    days = [(day, day_scenario(day, ai_cfg["scenario_weights"])) for day in range(lc["splits"]["fresh_test"][0], lc["splits"]["fresh_test"][1] + 1)]
    days += [(day, "S8_ai_prediction_error") for day in range(lc["splits"]["fresh_s8"][0], lc["splits"]["fresh_s8"][1] + 1)]
    for day, scenario in days:
        _, tables = simulate(cfg, scenarios, scenario, day, 42)
        sites = {s["site_id"]: s for s in tables["master/sites.csv"]}
        orders = {o["order_id"]: o for o in tables["orders/orders.csv"]}
        states = tables["runtime/site_state.csv"]
        features = [feature_row(s, sites[s["site_id"]], orders[s["order_id"]], tables["runtime/events.json"],
                                iso_to_min(s["timestamp"])) for s in states]
        Xday = np.array([[f[k] for k in FEATURES] for f in features])
        cached = {k: CachedEstimator(m, Xday, k == "classifier") for k, m in original_models.items()}
        predictor.b.update(cached)
        for index, state in enumerate(states):
            t = iso_to_min(state["timestamp"])
            site, order = sites[state["site_id"]], orders[state["order_id"]]
            events = tables["runtime/events.json"]
            result = predictor.predict(state, site, order, events, t, cfg["simulation"]["date"])
            if index in (0, len(states) // 2):
                predictor.b.update(original_models)
                direct = predictor.predict(state, site, order, events, t, cfg["simulation"]["date"])
                assert result == direct
                predictor.b.update(cached)
            assert not validate_prediction(result), result
            f = feature_row(state, site, order, events, t)
            f["readiness_revision"] = readiness_revision(events, order["order_id"], t)
            X = np.array([[f[k] for k in FEATURES]])
            b = predictor.b
            qlo, qhi = b["q_lo"].predict(X)[0], b["q_hi"].predict(X)[0]
            lo = max(0, min(qlo, qhi) - b["conformal_margin"])
            hi = max(0, max(qlo, qhi) + b["conformal_margin"])
            conf = b["confidence_model"].predict([hi - lo])[0]
            trigger = bool(out_of_range(f, b["feature_ranges"])) or conf < predictor.threshold
            trigger |= b["fallback_on_revision"] and f["readiness_revision"] and not f["rain"]
            expected = remaining(f, b["fallback"]) if trigger else max(0, b["regressor"].predict(X)[0])
            assert result["fallback_used"] == trigger
            assert iso_to_min(result["predicted_ready_time"]) == t + round(expected)
            checked += 1
            fallbacks += int(trigger)
        print(f"day {day}: {checked} checked, {fallbacks} fallback", flush=True)
    summary = dict(predictions_checked=checked, fallbacks=fallbacks, uncached_comparisons=len(days) * 2,
                   inference="real models batch-cached per day; production predictor logic called for every row",
                   G5_contract_and_parity=True)
    (HERE / "iteration_05/runtime_checks.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(summary)


if __name__ == "__main__":
    main()
