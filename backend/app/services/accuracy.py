"""Client question 2: quantified error of the forecasts the desk acted on."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

from app.core.errors import OutOfScopeError
from app.domain.alignment import pair_forecast_with_actuals
from app.domain.calibration import coverage
from app.domain.metrics import (
    group_by_forecast_band,
    group_by_hour_of_day,
    histogram,
    percentile,
    summarise,
)
from app.domain.selection import UK_TZ, issue_slot_label, local_day_window_utc
from app.services.common import (
    DayComparison,
    baseline_dto,
    compare_day,
    energy_dto,
    ensure_in_scope,
    format_cutoff,
    history_for,
    persistence_pairs,
)
from app.services.dto import (
    AccuracyReportDTO,
    BandBacktestDTO,
    CoverageOptionDTO,
    DailyAccuracyDTO,
    ErrorSummaryDTO,
    ForecastBandDTO,
    HistogramBinDTO,
    HistogramDTO,
    HourOfDayDTO,
    IssueSlotDTO,
    ProcurementGuidanceDTO,
    WorstHourDTO,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from app.core.config import Settings
    from app.data.repository import WindDataRepository
    from app.domain.models import ErrorPair

BACKTEST_TARGET_PCT = 90


def _dates(start: date, end: date) -> Iterator[date]:
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += timedelta(days=1)


def _daily_dto(day: DayComparison) -> DailyAccuracyDTO:
    summary = summarise(day.pairs) if day.pairs else None
    return DailyAccuracyDTO(
        decision_date=day.context.decision_date,
        delivery_date=day.context.delivery_date,
        issue_time=day.issue.issue_time if day.issue else None,
        hours_compared=len(day.pairs),
        summary=ErrorSummaryDTO.from_domain(summary) if summary else None,
        energy=energy_dto(day.pairs),
    )


def _worst(
    tagged: Sequence[tuple[DayComparison, ErrorPair]], *, over: bool, limit: int
) -> list[WorstHourDTO]:
    ordered = sorted(tagged, key=lambda item: item[1].error_mw, reverse=over)
    chosen = [item for item in ordered if (item[1].error_mw > 0) == over][:limit]
    return [
        WorstHourDTO(
            decision_date=day.context.decision_date,
            delivery_date=day.context.delivery_date,
            target_time=pair.target_time,
            forecast_mw=pair.forecast_mw,
            actual_mw=pair.actual_mw,
            error_mw=pair.error_mw,
        )
        for day, pair in chosen
    ]


def _by_issue_slot(
    repo: WindDataRepository, days: Sequence[DayComparison], cutoff_local: time
) -> list[IssueSlotDTO]:
    """For each publication slot on the decision day, the error had the desk used it.

    This answers "how much accuracy do we gain by waiting for a later issue?" Slots after
    the cutoff are included for context and flagged as not available.
    """
    buckets: dict[str, list[ErrorPair]] = defaultdict(list)
    day_counts: dict[str, set[date]] = defaultdict(set)
    for day in days:
        ctx = day.context
        decision_start, decision_end = local_day_window_utc(ctx.decision_date, UK_TZ)
        for issue in repo.issues_covering(ctx.delivery_start, ctx.delivery_end):
            if not decision_start <= issue.issue_time < decision_end:
                continue
            pairs = pair_forecast_with_actuals(
                issue.points_between(ctx.delivery_start, ctx.delivery_end), day.hourly_actuals
            )
            if not pairs:
                continue
            label = issue_slot_label(issue.issue_time, UK_TZ)
            buckets[label].extend(pairs)
            day_counts[label].add(ctx.decision_date)

    return [
        IssueSlotDTO(
            slot_label=label,
            available_at_cutoff=_label_to_time(label) <= cutoff_local,
            days=len(day_counts[label]),
            summary=ErrorSummaryDTO.from_domain(summarise(pairs)),
        )
        for label, pairs in sorted(buckets.items())
    ]


def _label_to_time(label: str) -> time:
    return datetime.strptime(label, "%H:%M").time()  # noqa: DTZ007 (wall-clock label only)


def _by_forecast_band(pairs: Sequence[ErrorPair], edges: Sequence[float]) -> list[ForecastBandDTO]:
    result: list[ForecastBandDTO] = []
    for band, members in group_by_forecast_band(pairs, edges).items():
        if not members:
            continue
        upper = None if math.isinf(band.upper_mw) else band.upper_mw
        label = (
            f"{band.lower_mw / 1000:g}-{band.upper_mw / 1000:g} GW"
            if upper is not None
            else f"≥ {band.lower_mw / 1000:g} GW"
        )
        result.append(
            ForecastBandDTO(
                label=label,
                lower_mw=band.lower_mw,
                upper_mw=upper,
                summary=ErrorSummaryDTO.from_domain(summarise(members)),
            )
        )
    return result


def _guidance(
    pairs: Sequence[ErrorPair], summary: ErrorSummaryDTO, cutoff_label: str, levels: Sequence[int]
) -> ProcurementGuidanceDTO:
    mean_actual = summary.mean_actual_mw
    errors = sorted(p.error_mw for p in pairs)
    options = [
        CoverageOptionDTO(
            confidence_pct=level,
            buffer_mw=(buffer := max(0.0, percentile(errors, level / 100.0)) if errors else 0.0),
            pct_of_mean_actual=(buffer / mean_actual * 100.0) if mean_actual else 0.0,
        )
        for level in levels
    ]
    pct = (summary.buffer_p90_mw / mean_actual * 100.0) if mean_actual else 0.0
    direction = "exceeded" if summary.bias_mw >= 0 else "fell below"
    explanation = (
        f"At the {cutoff_label} cutoff the forecast {direction} metered outturn by "
        f"{abs(summary.bias_mw):,.0f} MW on average. Under-delivery against forecast stayed "
        f"within {summary.buffer_p90_mw:,.0f} MW in 90% of hours. To be covered in 90% of "
        f"hours, plan for wind at {summary.buffer_p90_mw:,.0f} MW below forecast "
        f"({pct:.0f}% of mean outturn) and procure the difference."
    )
    return ProcurementGuidanceDTO(
        bias_mw=summary.bias_mw,
        buffer_p90_mw=summary.buffer_p90_mw,
        buffer_p90_pct_of_mean_actual=pct,
        coverage_options=options,
        explanation=explanation,
    )


def _band_backtest(
    repo: WindDataRepository, days: Sequence[DayComparison], cutoff_local: time, settings: Settings
) -> BandBacktestDTO | None:
    """Apply each day's *prior* 90% buffer to that day and count how often it held."""
    hours_checked = hours_covered = days_checked = days_without = 0
    for day in days:
        if not day.pairs:
            continue
        history = history_for(repo, day.context.decision_date, cutoff_local, settings)
        if history.calibration is None:
            days_without += 1
            continue
        covered, total = coverage(day.pairs, max(0.0, history.calibration.p90_mw))
        hours_covered += covered
        hours_checked += total
        days_checked += 1
    if hours_checked == 0:
        return None
    return BandBacktestDTO(
        target_pct=BACKTEST_TARGET_PCT,
        days_checked=days_checked,
        days_without_history=days_without,
        hours_checked=hours_checked,
        hours_covered=hours_covered,
        coverage_pct=hours_covered / hours_checked * 100.0,
    )


def build_accuracy_report(
    repo: WindDataRepository,
    from_decision: date,
    to_decision: date,
    cutoff_local: time,
    settings: Settings,
) -> AccuracyReportDTO:
    """Assemble the accuracy report over an inclusive range of decision days."""
    ensure_in_scope(from_decision, settings)
    ensure_in_scope(to_decision, settings)
    if to_decision < from_decision:
        msg = "to_date must not be before from_date."
        raise OutOfScopeError(msg)

    days = [compare_day(repo, d, cutoff_local) for d in _dates(from_decision, to_decision)]
    tagged = [(day, pair) for day in days for pair in day.pairs]
    all_pairs = [pair for _, pair in tagged]
    overall = ErrorSummaryDTO.from_domain(summarise(all_pairs))
    cutoff_label = format_cutoff(cutoff_local)

    baseline_pairs = [
        p
        for day in days
        for p in persistence_pairs(repo, day.context, settings.persistence_lag_hours)
    ]

    return AccuracyReportDTO(
        from_decision_date=from_decision,
        to_decision_date=to_decision,
        timezone=str(UK_TZ),
        cutoff_local=cutoff_label,
        days_requested=len(days),
        days_compared=sum(1 for day in days if day.pairs),
        days_without_forecast=[day.context.decision_date for day in days if day.issue is None],
        hours_compared=len(all_pairs),
        overall=overall,
        baseline=baseline_dto(baseline_pairs, all_pairs),
        guidance=_guidance(all_pairs, overall, cutoff_label, settings.coverage_levels_pct),
        band_backtest=_band_backtest(repo, days, cutoff_local, settings),
        daily=[_daily_dto(day) for day in days],
        by_hour_of_day=[
            HourOfDayDTO(hour=hour, summary=ErrorSummaryDTO.from_domain(summarise(pairs)))
            for hour, pairs in group_by_hour_of_day(all_pairs, UK_TZ).items()
        ],
        by_issue_slot=_by_issue_slot(repo, days, cutoff_local),
        by_forecast_band=_by_forecast_band(all_pairs, settings.forecast_band_edges_mw),
        histogram=HistogramDTO(
            bin_width_mw=settings.histogram_bin_width_mw,
            bins=[
                HistogramBinDTO(lower_mw=b.lower_mw, upper_mw=b.upper_mw, count=b.count)
                for b in histogram(all_pairs, settings.histogram_bin_width_mw)
            ],
        ),
        worst_over_forecast_hours=_worst(tagged, over=True, limit=settings.worst_hours_limit),
        worst_under_forecast_hours=_worst(tagged, over=False, limit=settings.worst_hours_limit),
    )


def export_rows(
    repo: WindDataRepository,
    from_decision: date,
    to_decision: date,
    cutoff_local: time,
    settings: Settings,
) -> Iterator[list[str]]:
    """Yield CSV rows (header first) of every compared hour, for the desk's spreadsheets."""
    ensure_in_scope(from_decision, settings)
    ensure_in_scope(to_decision, settings)
    yield [
        "decision_date",
        "delivery_date",
        "issue_time_utc",
        "target_time_utc",
        "forecast_mw",
        "actual_mw",
        "error_mw",
    ]
    for decision_date in _dates(from_decision, to_decision):
        day = compare_day(repo, decision_date, cutoff_local)
        if day.issue is None:
            continue
        for pair in day.pairs:
            yield [
                day.context.decision_date.isoformat(),
                day.context.delivery_date.isoformat(),
                day.issue.issue_time.isoformat(),
                pair.target_time.isoformat(),
                f"{pair.forecast_mw:.1f}",
                f"{pair.actual_mw:.1f}",
                f"{pair.error_mw:.1f}",
            ]
