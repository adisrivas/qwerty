from datetime import UTC, date, datetime, timedelta

from app.domain.alignment import floor_to_hour, hourly_mean, pair_forecast_with_actuals
from app.domain.models import ActualPoint, ForecastPoint, HourlyActual

T0 = datetime(2026, 1, 10, 3, 0, tzinfo=UTC)


def _actual(offset_minutes: int, mw: float) -> ActualPoint:
    return ActualPoint(
        target_time=T0 + timedelta(minutes=offset_minutes),
        generation_mw=mw,
        settlement_date=date(2026, 1, 10),
        settlement_period=7 + offset_minutes // 30,
    )


def test_floor_to_hour() -> None:
    assert floor_to_hour(datetime(2026, 1, 1, 5, 59, 59, 123, tzinfo=UTC)) == datetime(
        2026, 1, 1, 5, tzinfo=UTC
    )


def test_hourly_mean_averages_two_half_hours_and_flags_incomplete() -> None:
    result = hourly_mean([_actual(0, 100.0), _actual(30, 300.0), _actual(60, 500.0)])
    assert result[T0] == HourlyActual(target_time=T0, generation_mw=200.0, periods_used=2)
    assert result[T0].is_complete
    partial = result[T0 + timedelta(hours=1)]
    assert partial.generation_mw == 500.0
    assert not partial.is_complete


def test_hourly_mean_is_sorted_and_empty_input_gives_empty_dict() -> None:
    result = hourly_mean([_actual(60, 1.0), _actual(0, 2.0), _actual(30, 4.0)])
    assert list(result) == [T0, T0 + timedelta(hours=1)]
    assert hourly_mean([]) == {}


def test_pairing_skips_missing_and_incomplete_hours_and_sorts() -> None:
    issue_time = datetime(2026, 1, 9, 9, 30, tzinfo=UTC)
    forecasts = [
        ForecastPoint(issue_time, T0 + timedelta(hours=2), 999.0),  # no actual at all
        ForecastPoint(issue_time, T0 + timedelta(hours=1), 450.0),  # incomplete actual
        ForecastPoint(issue_time, T0, 250.0),  # complete actual, mean 200
    ]
    hourly = hourly_mean([_actual(0, 100.0), _actual(30, 300.0), _actual(60, 500.0)])
    pairs = pair_forecast_with_actuals(forecasts, hourly)
    assert len(pairs) == 1
    assert pairs[0].target_time == T0
    assert pairs[0].forecast_mw == 250.0
    assert pairs[0].actual_mw == 200.0
    assert pairs[0].error_mw == 50.0
