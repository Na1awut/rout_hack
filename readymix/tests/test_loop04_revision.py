"""Revision semantics and causality, independent of model accuracy."""
import copy
import pytest

from readymix.ai.fallback import readiness_revision, remaining
from readymix.ai.features import feature_row, records_from_day
from readymix.ai.predictor import SiteReadyPredictor, validate_prediction
from readymix.simulation.build_dataset import load_configs, simulate
from readymix.simulation.common import iso_to_min


@pytest.mark.parametrize("event_type,amount,expected", [
    ("SITE_READY_LATE", {"delay_min": 40}, 70),
    ("SITE_READY_EARLY", {"early_min": 20}, 10),
    ("SITE_DELAY", {"delay_min": 40}, 95),
    ("PUMP_FAILURE", {"delay_min": 40}, 95),
])
def test_hand_calculated_event_semantics(event_type, amount, expected):
    event = dict(order_id="O1", timestamp="2026-09-28T08:00:00", event_type=event_type, **amount)
    row = dict(t_rel_min=-30, hist_delay_mean=25, announced_delay_min=amount.get("delay_min", -amount.get("early_min", 0)),
               rain=0, readiness_revision=readiness_revision([event], "O1", 480))
    assert remaining(row, "event_history") == expected


def test_future_and_other_order_revisions_are_not_visible():
    event = dict(order_id="O1", timestamp="2026-09-28T08:00:00", event_type="SITE_READY_LATE")
    assert not readiness_revision([event], "O1", 479)
    assert not readiness_revision([event], "O2", 480)
    assert readiness_revision([event], "O1", 480)


def test_rain_keeps_uncertain_history_fallback():
    row = dict(t_rel_min=-30, hist_delay_mean=25, announced_delay_min=40, rain=1, readiness_revision=True)
    assert remaining(row, "event_history") == 95


def test_revision_metadata_independent_of_truth():
    sim, scenarios = load_configs()
    _, tables = simulate(sim, scenarios, "S8_ai_prediction_error", 4001, 42)
    changed = copy.deepcopy(tables)
    for r in changed["ground_truth/order_readiness.csv"]:
        r["actual_ready_time"] = "2026-09-28T23:00:00"
    a = records_from_day(tables, 4001, "S8_ai_prediction_error")
    b = records_from_day(changed, 4001, "S8_ai_prediction_error")
    assert [r["readiness_revision"] for r in a] == [r["readiness_revision"] for r in b]
    assert any(r["readiness_revision"] for r in a)


def test_live_revision_supersedes_ai_and_retains_additive_disruption():
    sim, scenarios = load_configs()
    _, tables = simulate(sim, scenarios, "S8_ai_prediction_error", 4001, 42)
    sites = {s["site_id"]: s for s in tables["master/sites.csv"]}
    orders = {o["order_id"]: o for o in tables["orders/orders.csv"]}
    event = next(e for e in tables["runtime/events.json"] if e["event_type"] == "SITE_READY_LATE")
    state = next(s for s in tables["runtime/site_state.csv"] if s["order_id"] == event["order_id"]
                 and s["timestamp"] >= event["timestamp"])
    t = iso_to_min(state["timestamp"])
    extra = dict(event, event_type="SITE_DELAY", delay_min=10)
    events = [event, extra]
    p = SiteReadyPredictor()
    p.b.update(fallback="event_history", fallback_on_revision=True)
    result = p.predict(state, sites[state["site_id"]], orders[state["order_id"]], events, t, sim["simulation"]["date"])
    expected = max(t, iso_to_min(orders[state["order_id"]]["requested_start"]) + event["delay_min"] + 10)
    assert iso_to_min(result["predicted_ready_time"]) == expected
    assert result["fallback_used"] and "revision" in result["fallback_reason"]
    assert not validate_prediction(result)
