import json
import shutil

import pytest

from readymix.application.buffered_dispatch import BufferedDispatch
from readymix.application.fleet_check import check_fleet
from readymix.application.safe_dispatch import run_safely
from readymix.simulation.build_dataset import generate
from readymix.simulation.executor import run_day


@pytest.fixture(scope="module")
def day(tmp_path_factory):
    return generate("S0_normal", 9301, tmp_path_factory.mktemp("d"), world_seed=42)


def _copy(day, tmp_path):
    root = tmp_path / "copy"
    shutil.copytree(day, root)
    return root


def _refresh(root):
    import hashlib
    m = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    m["files"] = {r: hashlib.sha256((root / r).read_bytes()).hexdigest() for r in m["files"]}
    (root / "manifest.json").write_text(json.dumps(m), encoding="utf-8")


def _set_vehicles(root, keep):
    p = root / "master/vehicles.csv"
    lines = p.read_text(encoding="utf-8").splitlines()
    p.write_text("\n".join(lines[:1 + keep]) + "\n", encoding="utf-8")
    _refresh(root)


def test_fleet_check_monotone_in_fleet_size(day, tmp_path):
    base = check_fleet(day)
    root = _copy(day, tmp_path)
    _set_vehicles(root, 3)
    small = check_fleet(root)
    assert small["status"] == "INFEASIBLE" and small["extra_trucks"] >= 1
    assert small["forecast_unserved"] >= base["forecast_unserved"]
    assert "เพิ่มรถอีก" in small["message"]


def test_no_trucks_is_a_status_not_a_crash(day, tmp_path):
    root = _copy(day, tmp_path)
    _set_vehicles(root, 0)
    out = run_safely(root)
    assert out["status"] in {"DEGRADED", "REJECTED_DATA"}
    assert out["messages"]


class _Crash:
    def predict(self, *a, **k):
        raise RuntimeError("boom")


def test_predictor_crash_falls_back_to_no_ai_decisions(day):
    out = run_safely(day, predictor=_Crash(), first_buffer_min=5, next_buffer_min=15)
    assert out["status"] == "DEGRADED" and out["predictor_failures"] > 0
    plain = run_day(day, BufferedDispatch(None, 5, 15), 5)
    assert out["result"]["log"] == plain["log"]


def test_missing_model_file_uses_no_ai_dispatch(day):
    out = run_safely(day, model="missing.joblib")
    assert out["status"] == "DEGRADED" and out["policy"] == "B_dynamic_buffered"
    assert any("AI ใช้ไม่ได้" in m for m in out["messages"])


def test_tampered_data_is_rejected(day, tmp_path):
    root = _copy(day, tmp_path)
    p = root / "orders/orders.csv"
    p.write_text(p.read_text(encoding="utf-8").replace(",ACTIVE", ",CANCELLED", 1), encoding="utf-8")
    out = run_safely(root)
    assert out["status"] == "REJECTED_DATA" and out["result"] is None
