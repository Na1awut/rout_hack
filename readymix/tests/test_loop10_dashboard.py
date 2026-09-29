from datetime import time

import pytest

from readymix.dashboard.trace import PHASE9, alerts, decisions, run_traced, site_status, truck_states

pytestmark = pytest.mark.skipif(not (PHASE9 / "datasets").exists(), reason="needs Phase 9 iteration_02 datasets")


@pytest.fixture(scope="module")
def day():
    return run_traced("S3_site_delay", 9101), run_traced("S3_site_delay", 9101, "A_static_planned")


def test_traced_run_is_the_phase9_run(day):
    for run in day:
        assert run["log_sha256"] == run["expected_sha256"]


def test_decisions_explain_every_ai_release(day):
    after, _ = day
    ds = decisions(after)
    assert len(ds) == len(after["audit"]) == sum("released" in lg for lg in after["log"].values())
    ai = [d for d in ds if d["reason"]["readiness_source"].startswith("site_ready_v3")]
    assert ai and all("predicted_site_ready" in d["reason"] and "delay_probability" in d["reason"] for d in ai)


def test_replay_never_shows_future_truth(day):
    after, _ = day
    for s in site_status(after, 420):
        assert s["actual_ready"] == "not yet" or s["actual_ready"] <= "07:00"
    early = {s["order"]: s["ai_predicted_ready"] for s in site_status(after, 420)}
    for oid, shown in early.items():
        seen = [p for p in after["predictions"] if p["order_id"] == oid and p["t"] <= 420]
        assert shown == (seen[-1]["predicted_ready_time"][11:16] if seen else "-")


def test_truck_states_one_per_truck(day):
    after, _ = day
    for t in range(360, 1200, 30):
        st = truck_states(after["log"], t)
        assert len(st) <= len(after["plan"].vehicles)
        assert all(s["since"] <= t < s["until"] for s in st.values())
    assert isinstance(alerts(after, 600), list)


def test_app_runs_headless():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(PHASE9.parents[1] / "readymix/dashboard/app.py"), default_timeout=180)
    at.run()
    assert not at.exception
    assert len(at.metric) == 7
    at.sidebar.slider[0].set_value(time(18, 30)).run()
    at.sidebar.button[0].click().run()
    assert not at.exception
