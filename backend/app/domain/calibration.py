"""Forward-looking uncertainty band from past errors, without look-ahead.

``dependable_mw`` is forecast - P90(error), ``expected_mw`` is forecast - P50(error) and
``optimistic_mw`` is forecast - P10(error). The caller decides which past days are admissible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from app.domain.metrics import percentile

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from app.domain.models import ErrorPair, ForecastPoint


@dataclass(frozen=True, slots=True)
class Calibration:
    """Empirical signed-error quantiles (MW) from a set of past hours."""

    hours: int
    bias_mw: float
    p10_mw: float
    p50_mw: float
    p90_mw: float

    def quantile(self, fraction: float, errors: Sequence[float]) -> float:
        """Any other quantile of the same errors (helper for coverage options)."""
        return percentile(sorted(errors), fraction)


@dataclass(frozen=True, slots=True)
class BandPoint:
    """The forecast for one hour with its calibrated range."""

    target_time: datetime
    forecast_mw: float
    dependable_mw: float
    expected_mw: float
    optimistic_mw: float


def calibrate(pairs: Sequence[ErrorPair]) -> Calibration | None:
    """Summarise past errors; ``None`` when there is nothing to learn from."""
    if not pairs:
        return None
    errors = sorted(p.error_mw for p in pairs)
    return Calibration(
        hours=len(errors),
        bias_mw=sum(errors) / len(errors),
        p10_mw=percentile(errors, 0.10),
        p50_mw=percentile(errors, 0.50),
        p90_mw=percentile(errors, 0.90),
    )


def apply_band(points: Iterable[ForecastPoint], calibration: Calibration) -> list[BandPoint]:
    """Shift each forecast point by the calibrated quantiles (never below zero)."""
    return [
        BandPoint(
            target_time=p.target_time,
            forecast_mw=p.generation_mw,
            dependable_mw=max(0.0, p.generation_mw - calibration.p90_mw),
            expected_mw=max(0.0, p.generation_mw - calibration.p50_mw),
            optimistic_mw=max(0.0, p.generation_mw - calibration.p10_mw),
        )
        for p in points
    ]


def coverage(pairs: Sequence[ErrorPair], buffer_mw: float) -> tuple[int, int]:
    """How many hours the actual stayed at or above ``forecast - buffer``.

    Returns ``(covered, total)``. Used to back-test a buffer: a 90% buffer should cover
    about 90% of hours it was not fitted on.
    """
    covered = sum(1 for p in pairs if p.actual_mw >= p.forecast_mw - buffer_mw)
    return covered, len(pairs)
