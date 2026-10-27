from datetime import UTC, datetime, timedelta

import pytest

from app.domain.calibration import apply_band, calibrate, coverage
from app.domain.metrics import group_by_forecast_band, skill_score
from app.domain.models import ErrorPair, ForecastPoint

T0 = datetime(2026, 1, 10, 0, 0, tzinfo=UTC)


def _pairs(errors: list[float], actual: float = 1000.0) -> list[ErrorPair]:
    return [
        ErrorPair(target_time=T0 + timedelta(hours=i), forecast_mw=actual + e, actual_mw=actual)
        for i, e in enumerate(errors)
    ]


def test_calibrate_quantiles_and_empty() -> None:
    assert calibrate([]) is None
    cal = calibrate(_pairs([-100.0, 100.0, 300.0, 500.0]))
    assert cal is not None
    assert cal.hours == 4
    assert cal.bias_mw == 200.0
    assert cal.p50_mw == 200.0
    assert cal.p10_mw == pytest.approx(-40.0)
    assert cal.p90_mw == pytest.approx(440.0)


def test_apply_band_shifts_by_quantiles_and_floors_at_zero() -> None:
    cal = calibrate(_pairs([-100.0, 100.0, 300.0, 500.0]))
    assert cal is not None
    issue_time = datetime(2026, 1, 9, 9, 30, tzinfo=UTC)
    points = [
        ForecastPoint(issue_time, T0, 1000.0),
        ForecastPoint(issue_time, T0 + timedelta(hours=1), 100.0),
    ]
    band = apply_band(points, cal)
    assert band[0].dependable_mw == pytest.approx(1000.0 - 440.0)
    assert band[0].expected_mw == pytest.approx(800.0)
    assert band[0].optimistic_mw == pytest.approx(1040.0)
    assert band[1].dependable_mw == 0.0  # 100 - 440 floors at zero


def test_coverage_counts_hours_within_buffer() -> None:
    pairs = _pairs([-100.0, 100.0, 300.0, 500.0])
    assert coverage(pairs, 300.0) == (3, 4)
    assert coverage(pairs, 0.0) == (1, 4)
    assert coverage([], 10.0) == (0, 0)


def test_skill_score() -> None:
    assert skill_score(50.0, 100.0) == pytest.approx(0.5)
    assert skill_score(100.0, 100.0) == 0.0
    assert skill_score(150.0, 100.0) == pytest.approx(-0.5)
    assert skill_score(10.0, 0.0) is None


def test_group_by_forecast_band_uses_half_open_bands() -> None:
    pairs = [
        ErrorPair(T0, 4999.0, 0.0),
        ErrorPair(T0 + timedelta(hours=1), 5000.0, 0.0),
        ErrorPair(T0 + timedelta(hours=2), 12000.0, 0.0),
        ErrorPair(T0 + timedelta(hours=3), 30000.0, 0.0),
    ]
    buckets = group_by_forecast_band(pairs, [5000.0, 10000.0, 15000.0])
    counts = [len(v) for v in buckets.values()]
    assert counts == [1, 1, 1, 1]
    labels = [(b.lower_mw, b.upper_mw) for b in buckets]
    assert labels[0] == (0.0, 5000.0)
    assert labels[-1][0] == 15000.0
