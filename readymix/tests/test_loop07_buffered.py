import pytest

from readymix.application.buffered_dispatch import BufferedDispatch
from readymix.application.dynamic_dispatch import DynamicDispatch
from readymix.application.execution_validator import validate_execution
from readymix.simulation.executor import run_day
from readymix.tests.test_loop02_execution import tiny_day


def test_zero_buffer_reproduces_dynamic_dispatch(tmp_path):
    root = tiny_day(tmp_path, n_trucks=2, n_trips=3)
    assert run_day(root, BufferedDispatch())["log"] == run_day(root, DynamicDispatch())["log"]


def test_buffers_release_earlier_and_stay_valid(tmp_path):
    root = tiny_day(tmp_path, n_trucks=3, n_trips=3)
    base = run_day(root, BufferedDispatch())
    buf = run_day(root, BufferedDispatch(first_buffer_min=15, next_buffer_min=15))
    assert validate_execution(buf, root) == []
    assert all("unload_end" in x for x in buf["log"].values())
    first = min(base["log"], key=lambda k: base["log"][k]["released"])
    assert buf["log"][first]["released"] < base["log"][first]["released"]
    assert run_day(root, BufferedDispatch(first_buffer_min=15, next_buffer_min=15))["log"] == buf["log"]


def test_negative_buffer_rejected():
    with pytest.raises(ValueError):
        BufferedDispatch(first_buffer_min=-5)


def test_name_keeps_policy_identity():
    assert BufferedDispatch().name == "B_dynamic_buffered"
    assert BufferedDispatch(object()).name == "C_ai_rolling_buffered"
