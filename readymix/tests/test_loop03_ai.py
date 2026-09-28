# Loop 3 tests: signals are causal, features take no labels, baselines are what they say
import inspect

import numpy as np
import pandas as pd

from readymix.ai import evaluation as ev
from readymix.ai.features import FEATURES, feature_row, records_from_day
from readymix.ai.training_data import day_scenario, load_ai_config, split_days
from readymix.simulation.build_dataset import load_configs, simulate
from readymix.simulation.common import iso_to_min


def _day(name="S5_pump_failure", seed=1001, world=42):
    sim, scen = load_configs()
    return simulate(sim, scen, name, seed, world)[1]


def test_world_seed_keeps_the_company_fixed():
    a, b = _day("S0_normal", 1001), _day("S0_normal", 1002)
    assert a["master/sites.csv"][0]["latitude"] == b["master/sites.csv"][0]["latitude"]
    assert a["master/vehicles.csv"] == b["master/vehicles.csv"]
    assert a["orders/orders.csv"] != b["orders/orders.csv"]


def test_default_world_seed_is_backward_compatible():
    sim, scen = load_configs()
    x = simulate(sim, scen, "S0_normal", 42)[1]
    y = simulate(sim, scen, "S0_normal", 42, 42)[1]
    assert x == y


def test_site_state_rows_stop_before_ready_and_never_see_later_reports():
    t = _day()
    ready = {r["order_id"]: iso_to_min(r["actual_ready_time"]) for r in t["ground_truth/order_readiness.csv"]}
    for r in t["runtime/site_state.csv"]:
        now = iso_to_min(r["timestamp"])
        assert now < ready[r["order_id"]]
        if r["minutes_since_report"] != "":
            assert int(r["minutes_since_report"]) >= 0
        assert 0 <= r["prep_progress_pct"] <= 90


def test_pump_down_only_after_the_failure_is_announced():
    t = _day()
    fail = {e["order_id"]: iso_to_min(e["timestamp"]) for e in t["runtime/events.json"] if e["event_type"] == "PUMP_FAILURE"}
    assert fail
    for r in t["runtime/site_state.csv"]:
        if r["pump_status"] == "DOWN":
            assert r["order_id"] in fail and iso_to_min(r["timestamp"]) >= fail[r["order_id"]]


def test_feature_row_takes_no_label_and_ignores_future_events():
    params = inspect.signature(feature_row).parameters
    assert not any(k in params for k in ("label", "truth", "actual", "ready"))
    t = _day()
    sites = {s["site_id"]: s for s in t["master/sites.csv"]}
    orders = {o["order_id"]: o for o in t["orders/orders.csv"]}
    ev_ = t["runtime/events.json"][0]
    row = next(r for r in t["runtime/site_state.csv"] if r["order_id"] == ev_["order_id"]
               and iso_to_min(r["timestamp"]) < iso_to_min(ev_["timestamp"]))
    now = iso_to_min(row["timestamp"])
    f = feature_row(row, sites[row["site_id"]], orders[row["order_id"]], t["runtime/events.json"], now)
    assert f["has_announcement"] == 0 and f["announced_delay_min"] == 0
    assert list(f) == FEATURES


def test_labels_match_ground_truth():
    t = _day()
    recs = pd.DataFrame(records_from_day(t, 1001, "S5_pump_failure"))
    assert (recs.remaining_min > 0).all()
    assert ((recs.planned + recs.ready_delay_min) == (recs.t + recs.remaining_min)).all()


def test_splits_are_disjoint_and_avoid_the_benchmark_day():
    cfg = load_ai_config()
    seen = set()
    for s in cfg["splits"]:
        days = set(split_days(cfg, s))
        assert not (days & seen)
        seen |= days
    assert 42 not in seen


def test_day_scenario_is_deterministic_and_never_s8():
    cfg = load_ai_config()
    names = [day_scenario(d, cfg["scenario_weights"]) for d in range(1001, 1101)]
    assert names == [day_scenario(d, cfg["scenario_weights"]) for d in range(1001, 1101)]
    assert "S8_ai_prediction_error" not in names


def test_baselines_by_hand():
    df = pd.DataFrame({"planned": [540, 540], "t": [500, 560], "hist_delay_mean": [10.0, 10.0],
                       "announced_delay_min": [30.0, 0.0], "hist_delay_std": [5.0, 5.0], "delay_so_far_min": [0, 20]})
    assert ev.baseline_remaining(df, "planned").tolist() == [40.0, 0.0]
    assert ev.baseline_remaining(df, "rule").tolist() == [70.0, 0.0]
    assert ev.baseline_remaining(df, "rule_hist").tolist() == [80.0, 0.0]
    p = ev.baseline_late_prob(df)
    assert p[1] == 1.0 and 0.99 < p[0] <= 1.0          # mean 40 >> 15


def test_metric_helpers():
    assert ev.mae([1, 2, 3], [1, 2, 5]) == 2 / 3
    assert ev.brier([0, 1], [0.0, 1.0]) == 0.0
    assert abs(ev.ece([0, 1, 1, 0], [0.5, 0.5, 0.5, 0.5])) < 1e-12
    df = pd.DataFrame({"day": [1, 1, 2], "order_id": ["a", "a", "b"]})
    lo, hi, mean = ev.paired_bootstrap(df, np.array([2.0, 2.0, 2.0]), np.array([1.0, 1.0, 1.0]), 200, 0)
    assert lo == hi == mean == 1.0
