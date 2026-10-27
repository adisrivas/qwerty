"""Helpers shared by the decision and accuracy services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

from app.core.errors import OutOfScopeError
from app.domain.alignment import pair_forecast_with_actuals
from app.domain.calibration import Calibration, calibrate
from app.domain.metrics import energy_mwh, skill_score, summarise
from app.domain.models import ErrorPair
from app.domain.selection import (
    UK_TZ,
    cutoff_instant_utc,
    delivery_date_for,
    local_day_window_utc,
    select_as_of_issue,
)
from app.services.dto import BaselineDTO, CalibrationDTO, EnergyDTO, ErrorPairDTO, PointDTO

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.core.config import Settings
    from app.data.repository import WindDataRepository
    from app.domain.models import ForecastIssue, HourlyActual

ASSUMPTIONS = [
    "Decision day D is the day the desk bids in the day-ahead auction. Delivery day is D+1.",
    "The forecast used is the latest WINDFOR issue published at or before the cutoff on D. "
    "The default cutoff is 09:50 UK time, the N2EX GB day-ahead gate closure.",
    "WINDFOR is hourly. FUELHH is half-hourly average MW and is averaged to the hour starting "
    "at the forecast timestamp before comparison.",
    "Error is forecast minus actual in MW. Positive error is under-delivery against forecast, "
    "the costly direction for a buyer.",
    "The calibrated band for a decision day uses errors from delivery days completed before "
    "that day only. No later information is used.",
    "The persistence baseline is the metered outturn at the same hour 48 hours earlier, the "
    "latest complete day known at a day-ahead cutoff.",
    "Both datasets cover transmission-connected wind in Great Britain. Embedded wind and other "
    "renewables are out of scope.",
    "Metered outturn includes curtailment instructed by the system operator, so part of any "
    "over-forecast is operational rather than meteorological.",
]

PERSISTENCE_NAME = "persistence_48h"


@dataclass(frozen=True, slots=True)
class DecisionContext:
    """All the instants that follow from a decision date and a cutoff time."""

    decision_date: date
    delivery_date: date
    cutoff_local: time
    cutoff_utc: datetime
    delivery_start: datetime
    delivery_end: datetime

    @classmethod
    def build(cls, decision_date: date, cutoff_local: time) -> DecisionContext:
        """Derive delivery date, cutoff instant and delivery window in UTC."""
        delivery_date = delivery_date_for(decision_date)
        start, end = local_day_window_utc(delivery_date, UK_TZ)
        return cls(
            decision_date=decision_date,
            delivery_date=delivery_date,
            cutoff_local=cutoff_local,
            cutoff_utc=cutoff_instant_utc(decision_date, cutoff_local, UK_TZ),
            delivery_start=start,
            delivery_end=end,
        )


@dataclass(frozen=True, slots=True)
class DayComparison:
    """The as-of forecast for one decision day paired with what actually happened."""

    context: DecisionContext
    issue: ForecastIssue | None
    hourly_actuals: dict[datetime, HourlyActual]
    pairs: list[ErrorPair]


@dataclass(frozen=True, slots=True)
class History:
    """Error history admissible on a decision day (delivery days completed before it)."""

    window_from: date
    window_to: date
    days_used: int
    pairs: list[ErrorPair]
    calibration: Calibration | None


def ensure_in_scope(decision_date: date, settings: Settings) -> None:
    """Reject decision dates outside the supported window with a clear message."""
    if not settings.first_decision_date <= decision_date <= settings.last_decision_date:
        msg = (
            f"decision_date {decision_date.isoformat()} is outside the supported range "
            f"{settings.first_decision_date.isoformat()} to "
            f"{settings.last_decision_date.isoformat()}."
        )
        raise OutOfScopeError(
            msg,
            supported_from=settings.first_decision_date.isoformat(),
            supported_to=settings.last_decision_date.isoformat(),
        )


def compare_day(repo: WindDataRepository, decision_date: date, cutoff_local: time) -> DayComparison:
    """Select the as-of issue for one decision day and pair it with hourly actuals."""
    context = DecisionContext.build(decision_date, cutoff_local)
    candidates = repo.issues_covering(context.delivery_start, context.delivery_end)
    issue = select_as_of_issue(candidates, context.cutoff_utc)
    hourly = repo.hourly_actuals_between(context.delivery_start, context.delivery_end)
    pairs: list[ErrorPair] = []
    if issue is not None:
        pairs = pair_forecast_with_actuals(
            issue.points_between(context.delivery_start, context.delivery_end), hourly
        )
    return DayComparison(context=context, issue=issue, hourly_actuals=hourly, pairs=pairs)


def history_for(
    repo: WindDataRepository, decision_date: date, cutoff_local: time, settings: Settings
) -> History:
    """Errors from delivery days that were complete before ``decision_date``.

    Delivery day D-1 ends at midnight before the decision day, so the newest admissible
    decision day is D-2. The window reaches back ``calibration_lookback_days`` delivery days.
    """
    newest = decision_date - timedelta(days=2)
    oldest = newest - timedelta(days=settings.calibration_lookback_days - 1)
    pairs: list[ErrorPair] = []
    days_used = 0
    cursor = oldest
    while cursor <= newest:
        day = compare_day(repo, cursor, cutoff_local)
        if day.pairs:
            pairs.extend(day.pairs)
            days_used += 1
        cursor += timedelta(days=1)
    calibration = calibrate(pairs) if days_used >= settings.calibration_min_days else None
    return History(
        window_from=oldest,
        window_to=newest,
        days_used=days_used,
        pairs=pairs,
        calibration=calibration,
    )


def persistence_pairs(
    repo: WindDataRepository, context: DecisionContext, lag_hours: int
) -> list[ErrorPair]:
    """Naive forecast: the actual at the same hour ``lag_hours`` earlier, vs the actual."""
    lag = timedelta(hours=lag_hours)
    hourly = repo.hourly_actuals_between(context.delivery_start, context.delivery_end)
    earlier = repo.hourly_actuals_between(context.delivery_start - lag, context.delivery_end - lag)
    pairs: list[ErrorPair] = []
    for target, actual in hourly.items():
        baseline = earlier.get(target - lag)
        if actual.is_complete and baseline is not None and baseline.is_complete:
            pairs.append(
                ErrorPair(
                    target_time=target,
                    forecast_mw=baseline.generation_mw,
                    actual_mw=actual.generation_mw,
                )
            )
    return pairs


def baseline_dto(
    baseline_pairs: Sequence[ErrorPair], forecast_pairs: Sequence[ErrorPair]
) -> BaselineDTO | None:
    """Summarise the naive baseline over the hours the real forecast was also scored on."""
    scored = {p.target_time for p in forecast_pairs}
    common = [p for p in baseline_pairs if p.target_time in scored]
    if not common:
        return None
    base = summarise(common)
    model = summarise(
        [p for p in forecast_pairs if p.target_time in {c.target_time for c in common}]
    )
    return BaselineDTO(
        name=PERSISTENCE_NAME,
        hours=base.count,
        mae_mw=base.mae_mw,
        bias_mw=base.bias_mw,
        skill_score=skill_score(model.mae_mw, base.mae_mw),
    )


def calibration_dto(history: History) -> CalibrationDTO | None:
    """Expose the calibration window and quantiles."""
    if history.calibration is None:
        return None
    c = history.calibration
    return CalibrationDTO(
        window_from_decision_date=history.window_from,
        window_to_decision_date=history.window_to,
        days_used=history.days_used,
        hours_used=c.hours,
        bias_mw=c.bias_mw,
        p10_mw=c.p10_mw,
        p50_mw=c.p50_mw,
        p90_mw=c.p90_mw,
    )


def format_cutoff(cutoff: time) -> str:
    """Render a cutoff as ``HH:MM``."""
    return cutoff.strftime("%H:%M")


def to_point_dtos(points: Sequence[tuple[datetime, float]]) -> list[PointDTO]:
    """Convert ``(time, mw)`` tuples to DTOs."""
    return [PointDTO(target_time=t, generation_mw=mw) for t, mw in points]


def to_pair_dtos(pairs: Sequence[ErrorPair]) -> list[ErrorPairDTO]:
    """Convert domain pairs to DTOs."""
    return [
        ErrorPairDTO(
            target_time=p.target_time,
            forecast_mw=p.forecast_mw,
            actual_mw=p.actual_mw,
            error_mw=p.error_mw,
        )
        for p in pairs
    ]


def energy_dto(pairs: Sequence[ErrorPair]) -> EnergyDTO | None:
    """Daily MWh totals over the compared hours (each pair is one hour)."""
    if not pairs:
        return None
    forecast = energy_mwh([p.forecast_mw for p in pairs])
    actual = energy_mwh([p.actual_mw for p in pairs])
    return EnergyDTO(
        hours=len(pairs),
        forecast_mwh=forecast,
        actual_mwh=actual,
        error_mwh=forecast - actual,
    )
