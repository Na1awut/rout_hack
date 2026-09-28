"""Check candidate runtime contract and batch/runtime parity on fresh days."""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from readymix.ai.predictor import SiteReadyPredictor, validate_prediction
from readymix.ai.features import feature_row, FEATURES
from readymix.ai.fallback import remaining
from readymix.ai.calibration import out_of_range
from readymix.simulation.build_dataset import load_configs, simulate
from readymix.simulation.common import iso_to_min


def main():
    predictor = SiteReadyPredictor(HERE / "iteration_04/candidate.joblib")
    cfg, scenarios = load_configs()
    checked, fallbacks = 0, 0
    for day, scenario in ((5001, "S0_normal"), (6001, "S8_ai_prediction_error")):
        _, tables = simulate(cfg, scenarios, scenario, day, 42)
        sites = {s["site_id"]: s for s in tables["master/sites.csv"]}
        orders = {o["order_id"]: o for o in tables["orders/orders.csv"]}
        for state in tables["runtime/site_state.csv"][::5]:
            t = iso_to_min(state["timestamp"])
            site, order = sites[state["site_id"]], orders[state["order_id"]]
            events = tables["runtime/events.json"]
            result = predictor.predict(state, site, order, events, t, cfg["simulation"]["date"])
            assert not validate_prediction(result), result
            f = feature_row(state, site, order, events, t)
            X = np.array([[f[k] for k in FEATURES]])
            b = predictor.b
            qlo, qhi = b["q_lo"].predict(X)[0], b["q_hi"].predict(X)[0]
            lo = max(0, min(qlo, qhi) - b["conformal_margin"])
            hi = max(0, max(qlo, qhi) + b["conformal_margin"])
            conf = b["confidence_model"].predict([hi - lo])[0]
            trigger = bool(out_of_range(f, b["feature_ranges"])) or conf < predictor.threshold
            expected = remaining(f, b["fallback"], b["fallback_history"]) if trigger else max(0, b["regressor"].predict(X)[0])
            assert result["fallback_used"] == trigger
            assert iso_to_min(result["predicted_ready_time"]) == t + round(expected)
            checked += 1
            fallbacks += int(trigger)
    summary = dict(predictions_checked=checked, fallbacks=fallbacks, G5_contract_and_parity=True)
    (HERE / "iteration_04/runtime_checks.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(summary)


if __name__ == "__main__":
    main()
