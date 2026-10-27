import math
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.metrics import (
    EMPTY_SUMMARY,
    HistogramBin,
    energy_mwh,
    group_by_hour_of_day,
    histogram,
    percentile,
    summarise,
)
from app.domain.models import ErrorPair

T0 = datetime(2026, 1, 10, 0, 0, tzinfo=UTC)


def _pairs(errors: list[float], actual: float = 1000.0) -> list[ErrorPair]:
    return [
        ErrorPair(target_time=T0 + timedelta(hours=i), forecast_mw=actual + e, actual_mw=actual)
        for i, e in enumerate(errors)
    ]


def test_percentile_matches_linear_interpolation() -> None:
    values = [1.0, 2.0, 3.0, 4.0]
    assert percentile(values, 0.0) == 1.0
    assert percentile(values, 1.0) == 4.0
    assert percentile(values, 0.5) == 2.5
    assert percentile(values, 0.9) == pytest.approx(3.7)
    assert percentile([7.0], 0.9) == 7.0


def test_percentile_rejects_bad_input() -> None:
    with pytest.raises(ValueError, match="at least one"):
        percentile([], 0.5)
    with pytest.raises(ValueError, match="between 0 and 1"):
        percentile([1.0], 1.5)


def test_summarise_hand_computed() -> None:
    # errors: +300, -100, +100, +500  -> mean 200, MAE 250, RMSE sqrt((9+1+1+25)e4/4)=300
    summary = summarise(_pairs([300.0, -100.0, 100.0, 500.0]))
    assert summary.count == 4
    assert summary.mean_actual_mw == 1000.0
    assert summary.mean_forecast_mw == 1200.0
    assert summary.bias_mw == 200.0
    assert summary.mae_mw == 250.0
    assert summary.rmse_mw == pytest.approx(300.0)
    assert summary.nmae_pct == pytest.approx(25.0)
    assert summary.p50_mw == 200.0  # sorted: -100, 100, 300, 500 -> midpoint 200
    assert summary.p10_mw == pytest.approx(-40.0)
    assert summary.p90_mw == pytest.approx(440.0)
    assert summary.max_over_forecast_mw == 500.0
    assert summary.max_under_forecast_mw == -100.0
    assert summary.buffer_p90_mw == pytest.approx(440.0)


def test_summarise_edge_cases() -> None:
    assert summarise([]) is EMPTY_SUMMARY
    all_under = summarise(_pairs([-50.0, -10.0]))
    assert all_under.max_over_forecast_mw == 0.0
    assert all_under.buffer_p90_mw == 0.0
    zero_actual = summarise(_pairs([5.0], actual=0.0))
    assert zero_actual.nmae_pct == 0.0


def test_energy_mwh() -> None:
    assert energy_mwh([100.0, 200.0]) == 300.0
    assert energy_mwh([100.0, 200.0], hours_per_value=0.5) == 150.0


def test_group_by_hour_of_day_uses_local_hour() -> None:
    pairs = _pairs([1.0] * 26)  # 26 consecutive hours from midnight UTC in January
    grouped = group_by_hour_of_day(pairs)
    assert list(grouped) == list(range(24))
    assert len(grouped[0]) == 2
    assert len(grouped[1]) == 2
    assert len(grouped[2]) == 1


def test_histogram_bins_are_zero_aligned_and_contiguous() -> None:
    bins = histogram(_pairs([-250.0, 0.0, 10.0, 1200.0]), bin_width_mw=500.0)
    assert bins == [
        HistogramBin(-500.0, 0.0, 1),
        HistogramBin(0.0, 500.0, 2),
        HistogramBin(500.0, 1000.0, 0),
        HistogramBin(1000.0, 1500.0, 1),
    ]
    assert histogram([], 500.0) == []
    with pytest.raises(ValueError, match="positive"):
        histogram(_pairs([1.0]), 0.0)


def test_rmse_never_below_mae() -> None:
    summary = summarise(_pairs([-1000.0, 10.0, 20.0, 3000.0]))
    assert summary.rmse_mw >= summary.mae_mw
    assert math.isfinite(summary.rmse_mw)
