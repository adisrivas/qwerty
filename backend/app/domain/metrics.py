"""Error statistics over paired forecast and actual hours.

Errors are ``forecast - actual`` in MW. ``summarise`` is the single source of every
statistic shown in the product. MAPE is deliberately absent: it is unstable in calm hours.
"""

from __future__ import annotations

import itertools
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.selection import UK_TZ

if TYPE_CHECKING:
    from collections.abc import Sequence
    from zoneinfo import ZoneInfo

    from app.domain.models import ErrorPair


@dataclass(frozen=True, slots=True)
class ErrorSummary:
    """Summary statistics for a set of hourly errors. All MW unless stated."""

    count: int
    mean_actual_mw: float
    mean_forecast_mw: float
    bias_mw: float
    mae_mw: float
    rmse_mw: float
    nmae_pct: float
    p10_mw: float
    p50_mw: float
    p90_mw: float
    max_over_forecast_mw: float
    max_under_forecast_mw: float

    @property
    def buffer_p90_mw(self) -> float:
        """Extra MW to procure over the forecast to be covered in 90% of hours (never < 0)."""
        return max(0.0, self.p90_mw)


EMPTY_SUMMARY = ErrorSummary(
    count=0,
    mean_actual_mw=0.0,
    mean_forecast_mw=0.0,
    bias_mw=0.0,
    mae_mw=0.0,
    rmse_mw=0.0,
    nmae_pct=0.0,
    p10_mw=0.0,
    p50_mw=0.0,
    p90_mw=0.0,
    max_over_forecast_mw=0.0,
    max_under_forecast_mw=0.0,
)


def percentile(sorted_values: Sequence[float], fraction: float) -> float:
    """Linear-interpolation percentile (the same convention as numpy's default).

    ``sorted_values`` must be sorted ascending and non-empty. ``fraction`` is in ``[0, 1]``.
    """
    if not sorted_values:
        msg = "percentile() needs at least one value"
        raise ValueError(msg)
    if not 0.0 <= fraction <= 1.0:
        msg = "fraction must be between 0 and 1"
        raise ValueError(msg)
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = fraction * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def summarise(pairs: Sequence[ErrorPair]) -> ErrorSummary:
    """Compute the full error summary for a set of paired hours."""
    if not pairs:
        return EMPTY_SUMMARY

    n = len(pairs)
    errors = sorted(p.error_mw for p in pairs)
    mean_actual = sum(p.actual_mw for p in pairs) / n
    mean_forecast = sum(p.forecast_mw for p in pairs) / n
    mae = sum(abs(e) for e in errors) / n

    return ErrorSummary(
        count=n,
        mean_actual_mw=mean_actual,
        mean_forecast_mw=mean_forecast,
        bias_mw=sum(errors) / n,
        mae_mw=mae,
        rmse_mw=math.sqrt(sum(e * e for e in errors) / n),
        nmae_pct=(mae / mean_actual * 100.0) if mean_actual > 0 else 0.0,
        p10_mw=percentile(errors, 0.10),
        p50_mw=percentile(errors, 0.50),
        p90_mw=percentile(errors, 0.90),
        max_over_forecast_mw=max(errors[-1], 0.0),
        max_under_forecast_mw=min(errors[0], 0.0),
    )


def skill_score(mae_model_mw: float, mae_baseline_mw: float) -> float | None:
    """``1 - MAE_model / MAE_baseline``: 0 means no better than the baseline, 1 is perfect.

    ``None`` when the baseline has zero error (nothing to compare against).
    """
    if mae_baseline_mw <= 0:
        return None
    return 1.0 - mae_model_mw / mae_baseline_mw


def energy_mwh(values_mw: Sequence[float], hours_per_value: float = 1.0) -> float:
    """Convert a series of average-MW values into energy in MWh."""
    return sum(values_mw) * hours_per_value


def group_by_hour_of_day(
    pairs: Sequence[ErrorPair], tz: ZoneInfo = UK_TZ
) -> dict[int, list[ErrorPair]]:
    """Bucket pairs by local hour of day (0-23)."""
    buckets: dict[int, list[ErrorPair]] = defaultdict(list)
    for pair in pairs:
        buckets[pair.target_time.astimezone(tz).hour].append(pair)
    return dict(sorted(buckets.items()))


@dataclass(frozen=True, slots=True)
class Band:
    """A half-open forecast-level band ``[lower_mw, upper_mw)``; ``upper_mw`` may be ``inf``."""

    lower_mw: float
    upper_mw: float


def group_by_forecast_band(
    pairs: Sequence[ErrorPair], edges_mw: Sequence[float]
) -> dict[Band, list[ErrorPair]]:
    """Bucket pairs by the forecast level, using ascending ``edges_mw`` as boundaries.

    Low-wind and high-wind hours have different error behaviour; this is what a buyer
    experiences as "calm days are easy, windy days are where we get caught out".
    """
    bounds = [0.0, *sorted(edges_mw), math.inf]
    bands = [Band(lo, hi) for lo, hi in itertools.pairwise(bounds)]
    buckets: dict[Band, list[ErrorPair]] = {band: [] for band in bands}
    for pair in pairs:
        for band in bands:
            if band.lower_mw <= pair.forecast_mw < band.upper_mw:
                buckets[band].append(pair)
                break
    return buckets


@dataclass(frozen=True, slots=True)
class HistogramBin:
    """A half-open error bin ``[lower_mw, upper_mw)`` and how many hours fell in it."""

    lower_mw: float
    upper_mw: float
    count: int


def histogram(pairs: Sequence[ErrorPair], bin_width_mw: float) -> list[HistogramBin]:
    """Fixed-width histogram of signed errors, with bin edges aligned to zero.

    Returns contiguous bins from the lowest to the highest occupied bin (empty bins in
    between are included with ``count == 0`` so charts have no gaps).
    """
    if bin_width_mw <= 0:
        msg = "bin_width_mw must be positive"
        raise ValueError(msg)
    if not pairs:
        return []

    counts: dict[int, int] = defaultdict(int)
    for pair in pairs:
        counts[math.floor(pair.error_mw / bin_width_mw)] += 1

    lowest, highest = min(counts), max(counts)
    return [
        HistogramBin(
            lower_mw=index * bin_width_mw,
            upper_mw=(index + 1) * bin_width_mw,
            count=counts.get(index, 0),
        )
        for index in range(lowest, highest + 1)
    ]
