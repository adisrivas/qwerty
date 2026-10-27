"""Index of decision days and application metadata."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from app import __version__
from app.domain.selection import UK_TZ
from app.services.common import ASSUMPTIONS, compare_day, format_cutoff
from app.services.dto import (
    DecisionDayDTO,
    DecisionDaysDTO,
    MetaDTO,
    SnapshotDTO,
    SnapshotFileDTO,
)

if TYPE_CHECKING:
    from datetime import time

    from app.core.config import Settings
    from app.data.repository import WindDataRepository


def build_decision_days(
    repo: WindDataRepository, cutoff_local: time, settings: Settings
) -> DecisionDaysDTO:
    """List every supported decision day with the issue that would be selected."""
    days: list[DecisionDayDTO] = []
    cursor = settings.first_decision_date
    while cursor <= settings.last_decision_date:
        day = compare_day(repo, cursor, cutoff_local)
        days.append(
            DecisionDayDTO(
                decision_date=day.context.decision_date,
                delivery_date=day.context.delivery_date,
                selected_issue_time=day.issue.issue_time if day.issue else None,
                hours_with_actuals=sum(1 for h in day.hourly_actuals.values() if h.is_complete),
            )
        )
        cursor += timedelta(days=1)
    return DecisionDaysDTO(cutoff_local=format_cutoff(cutoff_local), days=days)


def build_meta(repo: WindDataRepository, settings: Settings) -> MetaDTO:
    """Scope, defaults and data provenance."""
    extent = repo.extent()
    manifest = repo.manifest
    snapshot = None
    if manifest is not None:
        snapshot = SnapshotDTO(
            created_at=manifest.created_at,
            source_base_url=manifest.source_base_url,
            windfor=SnapshotFileDTO(**manifest.windfor.model_dump()),
            fuelhh=SnapshotFileDTO(**manifest.fuelhh.model_dump()),
            notes=manifest.notes,
        )
    return MetaDTO(
        app_name=settings.app_name,
        version=__version__,
        environment=settings.environment,
        timezone=str(UK_TZ),
        first_decision_date=settings.first_decision_date,
        last_decision_date=settings.last_decision_date,
        default_cutoff_local=format_cutoff(settings.default_cutoff),
        calibration_lookback_days=settings.calibration_lookback_days,
        calibration_min_days=settings.calibration_min_days,
        persistence_lag_hours=settings.persistence_lag_hours,
        forecast_issue_count=extent.issue_count,
        actual_point_count=extent.actual_count,
        snapshot=snapshot,
        assumptions=ASSUMPTIONS,
    )
