"""The boundary validator must reject corrupt predictions without crashing."""
import pytest

from readymix.ai.predictor import validate_prediction


def prediction():
    return dict(site_id="S001", order_id="O001", prediction_time="2026-09-28T08:00:00",
                predicted_ready_time="2026-09-28T09:00:00", ready_delay_min=0,
                interval_min=[45.0, 75.0], predicted_service_min=15.0,
                delay_probability=0.2, confidence=0.8, model_version="test",
                fallback_used=False, fallback_reason=None)


def test_valid_contract():
    assert validate_prediction(prediction()) == []


@pytest.mark.parametrize("change", [
    {"prediction_time": "bad-date"},
    {"predicted_ready_time": "2026-09-28T09:00:00+07:00"},
    {"predicted_ready_time": "2026-09-28T07:00:00"},
    {"interval_min": ["a", 5]}, {"interval_min": [float("nan"), 5]},
    {"interval_min": [0, float("inf")]}, {"interval_min": [-1, 5]},
    {"interval_min": [8, 5]}, {"interval_min": []},
    {"predicted_service_min": float("nan")}, {"predicted_service_min": 0},
    {"ready_delay_min": True}, {"confidence": float("nan")},
    {"fallback_used": True}, {"fallback_reason": "unexpected"},
])
def test_rejects_malformed_contract(change):
    assert validate_prediction({**prediction(), **change})


@pytest.mark.parametrize("payload", [None, [], "invalid", {}, {"site_id": 1}])
def test_rejects_missing_or_non_mapping_payload(payload):
    assert validate_prediction(payload)
