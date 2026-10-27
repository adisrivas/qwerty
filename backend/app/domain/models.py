"""Domain vocabulary.

Conventions used everywhere in the domain layer:

* All ``datetime`` values are timezone-aware and expressed in UTC.
* ``generation_mw`` is power in megawatts (MW). For actuals it is the average over the
  half-hour; for forecasts it is the value NESO published for the hour starting at
  ``target_time``.
* ``target_time`` is the start of the interval the value describes (Elexon ``startTime``).
* ``issue_time`` is when a forecast was published (Elexon ``publishTime``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    """One forecast value for one hour, from one published issue."""

    issue_time: datetime
    target_time: datetime
    generation_mw: float


@dataclass(frozen=True, slots=True)
class ForecastIssue:
    """A complete forecast publication (one ``publishTime``) with its hourly points.

    ``points`` is sorted by ``target_time`` and contains no duplicate target times.
    """

    issue_time: datetime
    points: tuple[ForecastPoint, ...]

    @property
    def first_target(self) -> datetime:
        """Earliest hour covered by this issue."""
        return self.points[0].target_time

    @property
    def last_target(self) -> datetime:
        """Latest hour covered by this issue."""
        return self.points[-1].target_time

    def points_between(self, start: datetime, end: datetime) -> tuple[ForecastPoint, ...]:
        """Return points with ``start <= target_time < end``."""
        return tuple(p for p in self.points if start <= p.target_time < end)


@dataclass(frozen=True, slots=True)
class ActualPoint:
    """One measured half-hourly wind outturn (Elexon FUELHH, fuelType WIND)."""

    target_time: datetime
    generation_mw: float
    settlement_date: date
    settlement_period: int


@dataclass(frozen=True, slots=True)
class HourlyActual:
    """Measured outturn aggregated to the hour starting at ``target_time``.

    ``periods_used`` is how many half-hour values were averaged. A complete hour has 2.
    Incomplete hours are kept so the UI can show them, but they are never used in metrics.
    """

    target_time: datetime
    generation_mw: float
    periods_used: int

    @property
    def is_complete(self) -> bool:
        """True when both half-hours of the hour were available."""
        return self.periods_used == 2


@dataclass(frozen=True, slots=True)
class ErrorPair:
    """A forecast and the matching hourly actual, with the signed error.

    ``error_mw = forecast_mw - actual_mw``. Positive means the forecast was too high, which
    for a buyer is the dangerous direction: less wind arrived than planned, so more power
    had to be bought at short notice.
    """

    target_time: datetime
    forecast_mw: float
    actual_mw: float

    @property
    def error_mw(self) -> float:
        """Signed error, forecast minus actual, in MW."""
        return self.forecast_mw - self.actual_mw
