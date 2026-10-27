"""Align hourly forecasts with half-hourly actuals.

Both series are average MW, so the hourly actual is the mean of the two half-hours in the
hour. The forecast is never interpolated to half-hours.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING

from app.domain.models import ErrorPair, HourlyActual

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from app.domain.models import ActualPoint, ForecastPoint

HALF_HOURS_PER_HOUR = 2


def floor_to_hour(moment: datetime) -> datetime:
    """Return ``moment`` with minutes, seconds and microseconds set to zero."""
    return moment.replace(minute=0, second=0, microsecond=0)


def hourly_mean(actuals: Iterable[ActualPoint]) -> dict[datetime, HourlyActual]:
    """Aggregate half-hourly actuals to hourly means keyed by the hour start.

    Hours with only one half-hour value are returned with ``periods_used == 1`` so that the
    caller can display them but exclude them from error statistics.
    """
    buckets: dict[datetime, list[float]] = defaultdict(list)
    for point in actuals:
        buckets[floor_to_hour(point.target_time)].append(point.generation_mw)

    return {
        hour: HourlyActual(
            target_time=hour,
            generation_mw=sum(values) / len(values),
            periods_used=len(values),
        )
        for hour, values in sorted(buckets.items())
    }


def pair_forecast_with_actuals(
    forecast_points: Iterable[ForecastPoint],
    hourly_actuals: Mapping[datetime, HourlyActual],
) -> list[ErrorPair]:
    """Match each forecast hour with its complete hourly actual.

    Hours without a complete actual are skipped. The result is sorted by ``target_time``.
    """
    pairs: list[ErrorPair] = []
    for point in sorted(forecast_points, key=lambda p: p.target_time):
        actual = hourly_actuals.get(point.target_time)
        if actual is None or not actual.is_complete:
            continue
        pairs.append(
            ErrorPair(
                target_time=point.target_time,
                forecast_mw=point.generation_mw,
                actual_mw=actual.generation_mw,
            )
        )
    return pairs
