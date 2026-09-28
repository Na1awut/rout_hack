import json
from types import SimpleNamespace

from readymix.application.dynamic_dispatch import DynamicDispatch
from readymix.application.execution_validator import validate_execution
from readymix.simulation.executor import run_day
from readymix.tests.test_loop02_execution import tiny_day, _write
from readymix.tests.test_loop05_dispatch import Forecast


class CountingForecast(Forecast):
    def __init__(self, ready=600, fail=False):
        super().__init__(ready)
        self.calls = 0
        self.fail = fail

    def predict(self, *args):
        self.calls += 1
        if self.fail:
            raise RuntimeError("injected model failure")
        return super().predict(*args)


def test_interval_and_event_refresh_only_for_rolling():
    for rolling in (False, True):
        model = CountingForecast()
        policy = DynamicDispatch(model, rolling=rolling)
        policy.plan = SimpleNamespace(orders={"O1": dict(site_id="S1", order_id="O1", requested_start_min=540,
                                                       requested_start="2026-10-01T09:00")}, sites={"S1":dict(site_id="S1")})
        policy.cache, policy.calls, policy.failures = {}, 0, 0
        events = []
        obs = SimpleNamespace(t=480, site_reported_ready=lambda oid:False, site_state=lambda oid:{}, events=lambda:events)
        policy.readiness(obs, "O1", 0)
        obs.t = 485
        policy.readiness(obs, "O1", 0)
        assert model.calls == 1
        events.append(dict(event_id="E1", order_id="O1"))
        policy.readiness(obs, "O1", 20)
        assert model.calls == (2 if rolling else 1)
        obs.t = 500
        policy.readiness(obs, "O1", 20)
        assert model.calls == (3 if rolling else 1)


def test_predictor_failure_graceful_and_breakdown_respected(tmp_path):
    root = tiny_day(tmp_path, 3, 3, "10:00")
    _write(root / "runtime/site_state.csv", [dict(order_id="O1", site_id="S1", timestamp="2026-10-01T07:30")])
    (root / "runtime/events.json").write_text(json.dumps([dict(event_id="E1", timestamp="2026-10-01T06:00",
        event_type="TRUCK_BREAKDOWN", vehicle_id="T1")]))
    policy = DynamicDispatch(CountingForecast(fail=True))
    result = run_day(root, policy)
    assert policy.failures > 0
    assert all(lg.get("truck") != "T1" for lg in result["log"].values())
    assert validate_execution(result, root) == []


def test_policy_cannot_reassign_or_mutate_committed_loads(tmp_path):
    root = tiny_day(tmp_path, 3, 3, "10:00")
    _write(root / "runtime/site_state.csv", [dict(order_id="O1", site_id="S1", timestamp="2026-10-01T07:30")])
    class AuditedPolicy(DynamicDispatch):
        def decide(self, obs):
            committed = {tr["trip_id"]: obs.trip(tr["trip_id"]) for tr in self.plan.trips if obs.released(tr["trip_id"])}
            # Force the forecast to change while earlier loads are in flight.
            self.predictor.ready = 540 if obs.t < 525 else 600
            chosen = super().decide(obs)
            assert not set(chosen) & set(committed)
            assert committed == {tid:obs.trip(tid) for tid in committed}
            return chosen
    result = run_day(root, AuditedPolicy(CountingForecast()))
    assert validate_execution(result, root) == []


def test_capacity_validator_catches_overload(tmp_path):
    root = tiny_day(tmp_path, 1, 1)
    result = run_day(root, DynamicDispatch())
    result["log"]["O1-01"]["truck"] = "T1"
    path = root / "master/vehicles.csv"
    path.write_text(path.read_text().replace('6.0', '5.0'))
    assert any("capacity" in e for e in validate_execution(result, root))
