import copy
from pathlib import Path

import joblib
import numpy as np
import pytest

from readymix.ai.features import service_records_from_day
from readymix.ai.predictor import SiteReadyPredictor, validate_prediction
from readymix.ai.fallback import remaining, fit_history
from readymix.simulation.build_dataset import load_configs, simulate
from readymix.simulation.common import iso_to_min


class Output:
    def __init__(self, value):
        self.value = value

    def predict(self, X):
        return np.full(len(X), self.value)


@pytest.fixture
def inputs():
    sim, scenarios = load_configs()
    _, tables = simulate(sim, scenarios, "S0_normal", 42)
    st = tables["runtime/site_state.csv"][0]
    site = next(s for s in tables["master/sites.csv"] if s["site_id"] == st["site_id"])
    order = next(o for o in tables["orders/orders.csv"] if o["order_id"] == st["order_id"])
    return st, site, order, [], iso_to_min(st["timestamp"]), sim["simulation"]["date"]


def model():
    p = SiteReadyPredictor()
    # Force in-range so tests exercise the specified failure branch.
    p.b["feature_ranges"] = {}
    return p


def test_low_confidence_always_falls_back_even_for_old_bundle(inputs):
    p = model()
    p.b["fallback_on_low_confidence"] = False
    p.b["confidence_model"] = Output(0.1)
    result = p.predict(*inputs)
    assert result["fallback_used"] and "low confidence" in result["fallback_reason"]
    assert result["confidence"] == 0 and not validate_prediction(result)


@pytest.mark.parametrize("part", ["regressor", "q_lo", "confidence_model"])
@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_nonfinite_model_output_falls_back(inputs, part, value):
    p = model()
    p.b[part] = Output(value)
    result = p.predict(*inputs)
    assert result["fallback_used"] and not validate_prediction(result)


def test_future_state_falls_back(inputs):
    st, site, order, events, t, date = inputs
    result = model().predict(st, site, order, events, t - 1, date)
    assert result["fallback_used"] and "bad input" in result["fallback_reason"]


def test_required_identity_is_rejected_explicitly(inputs):
    st, site, order, events, t, date = inputs
    with pytest.raises(ValueError, match="identity"):
        model().predict(st, {}, order, events, t, date)


def test_service_features_do_not_change_when_labels_change():
    sim, scenarios = load_configs()
    _, tables = simulate(sim, scenarios, "S0_normal", 42)
    first = service_records_from_day(tables, 42, "S0_normal")
    changed = copy.deepcopy(tables)
    for row in changed["ground_truth/trip_service.csv"]:
        row["actual_unload_min"] += 100
    second = service_records_from_day(changed, 42, "S0_normal")
    for a, b in zip(first, second):
        assert a.pop("actual_unload_min") != b.pop("actual_unload_min")
        assert a == b and a["prev_actual_unload"] == -1


def test_conditional_history_remains_positive_after_mean_ready_time():
    row = dict(t_rel_min=30, hist_delay_mean=10, announced_delay_min=0, hist_delay_std=5)
    assert remaining(row, "rule_hist") == 0
    assert remaining(row, "conditional_history") > 0
