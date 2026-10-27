"""Client question 1: the latest forecast available at decision time."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.calibration import apply_band
from app.domain.metrics import summarise
from app.domain.selection import UK_TZ, issue_slot_label
from app.services.common import (
    DecisionContext,
    baseline_dto,
    calibration_dto,
    compare_day,
    energy_dto,
    ensure_in_scope,
    format_cutoff,
    history_for,
    persistence_pairs,
    to_pair_dtos,
    to_point_dtos,
)
from app.services.dto import (
    BandPointDTO,
    DecisionViewDTO,
    ErrorSummaryDTO,
    HourlyActualDTO,
    IssueDTO,
    WindowDTO,
)

if TYPE_CHECKING:
    from datetime import date, time

    from app.core.config import Settings
    from app.data.repository import WindDataRepository
    from app.domain.models import ForecastIssue

HOURS_PER_DAY = 24


def _issue_dto(issue: ForecastIssue, context: DecisionContext) -> IssueDTO:
    points = issue.points_between(context.delivery_start, context.delivery_end)
    delta_minutes = int((context.cutoff_utc - issue.issue_time).total_seconds() // 60)
    return IssueDTO(
        issue_time=issue.issue_time,
        slot_label=issue_slot_label(issue.issue_time, UK_TZ),
        available_at_cutoff=issue.issue_time <= context.cutoff_utc,
        minutes_before_cutoff=delta_minutes,
        coverage_hours=len(points),
        points=to_point_dtos([(p.target_time, p.generation_mw) for p in points]),
    )


def build_decision_view(
    repo: WindDataRepository, decision_date: date, cutoff_local: time, settings: Settings
) -> DecisionViewDTO:
    """Assemble the decision view for one decision day."""
    ensure_in_scope(decision_date, settings)
    comparison = compare_day(repo, decision_date, cutoff_local)
    context = comparison.context

    covering = repo.issues_covering(context.delivery_start, context.delivery_end)
    issue_dtos = [_issue_dto(issue, context) for issue in covering]
    selected = _issue_dto(comparison.issue, context) if comparison.issue is not None else None

    history = history_for(repo, decision_date, cutoff_local, settings)
    band: list[BandPointDTO] = []
    if comparison.issue is not None and history.calibration is not None:
        band = [
            BandPointDTO(
                target_time=b.target_time,
                forecast_mw=b.forecast_mw,
                dependable_mw=b.dependable_mw,
                expected_mw=b.expected_mw,
                optimistic_mw=b.optimistic_mw,
            )
            for b in apply_band(
                comparison.issue.points_between(context.delivery_start, context.delivery_end),
                history.calibration,
            )
        ]

    half_hourly = repo.actuals_between(context.delivery_start, context.delivery_end)
    hourly = [
        HourlyActualDTO(
            target_time=h.target_time,
            generation_mw=h.generation_mw,
            periods_used=h.periods_used,
            is_complete=h.is_complete,
        )
        for h in comparison.hourly_actuals.values()
    ]

    notes: list[str] = []
    if selected is None:
        notes.append(
            "No WINDFOR issue was published before the cutoff. The desk would have relied on "
            "an earlier issue or external information."
        )
    elif selected.coverage_hours < HOURS_PER_DAY:
        notes.append(
            f"The selected issue covers {selected.coverage_hours} of {HOURS_PER_DAY} hours "
            "of the delivery day."
        )
    if history.calibration is None:
        notes.append(
            f"No calibrated band: {history.days_used} completed day(s) of history before this "
            f"decision, minimum {settings.calibration_min_days}."
        )
    if not half_hourly:
        notes.append("No metered outturn is available for this delivery day.")
    elif comparison.pairs and len(comparison.pairs) < len(hourly):
        notes.append(
            f"{len(hourly) - len(comparison.pairs)} hour(s) excluded from error statistics "
            "because a half-hour actual is missing."
        )

    summary = summarise(comparison.pairs) if comparison.pairs else None
    baseline = baseline_dto(
        persistence_pairs(repo, context, settings.persistence_lag_hours), comparison.pairs
    )

    return DecisionViewDTO(
        decision_date=context.decision_date,
        delivery_date=context.delivery_date,
        timezone=str(UK_TZ),
        cutoff_local=format_cutoff(context.cutoff_local),
        cutoff_utc=context.cutoff_utc,
        delivery_window=WindowDTO(start=context.delivery_start, end=context.delivery_end),
        selected_issue=selected,
        issues=issue_dtos,
        calibration=calibration_dto(history),
        band=band,
        dependable_energy_mwh=sum(b.dependable_mw for b in band) if band else None,
        actuals_half_hourly=to_point_dtos([(a.target_time, a.generation_mw) for a in half_hourly]),
        actuals_hourly=hourly,
        comparison=to_pair_dtos(comparison.pairs),
        summary=ErrorSummaryDTO.from_domain(summary) if summary else None,
        baseline=baseline,
        energy=energy_dto(comparison.pairs),
        notes=notes,
    )
