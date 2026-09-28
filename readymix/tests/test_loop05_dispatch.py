import copy
import pytest

from readymix.application.extended_solver import DispatchJob, best_release, solve_dispatch
from readymix.application.dynamic_dispatch import DynamicDispatch
from readymix.application.execution_validator import validate_execution
from readymix.simulation.executor import run_day, Engine, Observation
from readymix.tests.test_loop02_execution import tiny_day, _write


def test_optimal_release_by_hand():
    assert best_release(DispatchJob("one", 550, 38), 480, 1080, 5) == (510, 2)
    assert best_release(DispatchJob("one", 550, 38), 520, 1080, 5) == (520, 8)
    assert best_release(DispatchJob("one", 550, 38), 1080, 1080, 5) is None


def test_prediction_changes_release_decision():
    assert solve_dispatch([DispatchJob("one", 540, 40)], 500, 1080, 1)[0] == ["one"]
    assert solve_dispatch([DispatchJob("one", 580, 40)], 500, 1080, 1)[0] == []


def test_slots_limit_and_priority_for_overdue_jobs():
    jobs = [DispatchJob("a", 500, 40), DispatchJob("b", 510, 40, 3)]
    assert solve_dispatch(jobs, 500, 1080, 0)[0] == []
    assert solve_dispatch(jobs, 500, 1080, 1)[0] == ["b"]


def test_exact_cost_matches_brute_force():
    for target in range(480, 620, 7):
        j = DispatchJob("x", target, 38)
        got = best_release(j, 500, 605, 5, 2, 4)
        expected = min(((t, 2 * max(0, target-t-38) + 4 * max(0, t+38-target))
                        for t in range(500, 605, 5)), key=lambda x: (x[1], x[0]))
        assert got == expected


def test_new_scheduler_valid_and_deterministic(tmp_path):
    root = tiny_day(tmp_path, n_trucks=2, n_trips=3)
    a, b = run_day(root, DynamicDispatch()), run_day(root, DynamicDispatch())
    assert a["log"] == b["log"]
    assert validate_execution(a, root) == []
    assert all("unload_end" in x for x in a["log"].values())


def test_observed_reports_are_causal_copies(tmp_path):
    root = tiny_day(tmp_path)
    _write(root / "runtime/site_state.csv", [dict(order_id="O1", timestamp="2026-10-01T08:00", value=1),
                                            dict(order_id="O1", timestamp="2026-10-01T09:00", value=2)])
    engine = Engine(root, DynamicDispatch())
    assert Observation(479, engine.plan, engine).site_state("O1") is None
    obs = Observation(480, engine.plan, engine)
    value = obs.site_state("O1")
    assert value["value"] == "1"
    value["value"] = "corrupt"
    assert obs.site_state("O1")["value"] == "1"


def test_future_truth_does_not_change_earlier_decisions(tmp_path):
    a = run_day(tiny_day(tmp_path / "a", 3, 3, "10:30"), DynamicDispatch())
    b = run_day(tiny_day(tmp_path / "b", 3, 3, "11:30"), DynamicDispatch())
    for tid, lg in a["log"].items():
        if lg.get("released", 1440) < 630:
            assert lg["released"] == b["log"][tid]["released"]


class Forecast:
    def __init__(self, ready):
        self.ready = ready

    def predict(self, state, site, order, events, t, date):
        from readymix.ai.predictor import _iso
        return dict(site_id=site["site_id"], order_id=order["order_id"], prediction_time=_iso(date, t),
                    predicted_ready_time=_iso(date, max(t, self.ready)), ready_delay_min=0,
                    interval_min=[0, 0], predicted_service_min=15., delay_probability=0., confidence=1.,
                    model_version="test", fallback_used=False, fallback_reason=None)


def test_live_prediction_shifts_loading_without_breaking_locks(tmp_path):
    root = tiny_day(tmp_path, 2, 2, "10:00")
    _write(root / "runtime/site_state.csv", [dict(order_id="O1", site_id="S1", timestamp="2026-10-01T07:30")])
    a = run_day(root, DynamicDispatch(Forecast(540)))
    b = run_day(root, DynamicDispatch(Forecast(600)))
    assert b["log"]["O1-01"]["load_start"] > a["log"]["O1-01"]["load_start"]
    assert validate_execution(a, root) == validate_execution(b, root) == []
