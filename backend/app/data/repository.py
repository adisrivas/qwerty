"""In-memory repository over parsed forecast issues and actuals.

Built once at application start from the snapshot. All lookups are by time window and use
binary search over sorted tuples, so each request costs microseconds.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from app.data.parsers import parse_actual_rows, parse_forecast_rows
from app.data.snapshot import SnapshotManifest, load_snapshot
from app.domain.alignment import hourly_mean
from app.domain.selection import issues_covering

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path
    from typing import Any

    from app.domain.models import ActualPoint, ForecastIssue, HourlyActual


@dataclass(frozen=True, slots=True)
class DataExtent:
    """The time range the repository can answer questions about."""

    first_issue_time: datetime | None
    last_issue_time: datetime | None
    issue_count: int
    first_actual_time: datetime | None
    last_actual_time: datetime | None
    actual_count: int


class WindDataRepository:
    """Read-only access to forecasts and actuals."""

    def __init__(
        self,
        issues: Iterable[ForecastIssue],
        actuals: Iterable[ActualPoint],
        manifest: SnapshotManifest | None = None,
    ) -> None:
        self._issues: tuple[ForecastIssue, ...] = tuple(
            sorted(issues, key=lambda issue: issue.issue_time)
        )
        self._actuals: tuple[ActualPoint, ...] = tuple(
            sorted(actuals, key=lambda point: point.target_time)
        )
        self._actual_times = [point.target_time for point in self._actuals]
        self.manifest = manifest

    @classmethod
    def from_rows(
        cls,
        windfor_rows: Iterable[Mapping[str, Any]],
        fuelhh_rows: Iterable[Mapping[str, Any]],
        manifest: SnapshotManifest | None = None,
    ) -> WindDataRepository:
        """Build from raw Elexon rows (used by tests and by the snapshot loader)."""
        return cls(parse_forecast_rows(windfor_rows), parse_actual_rows(fuelhh_rows), manifest)

    @classmethod
    def from_snapshot(cls, directory: Path) -> WindDataRepository:
        """Load and verify the committed snapshot, then parse it."""
        snapshot = load_snapshot(directory)
        return cls.from_rows(snapshot.windfor_rows, snapshot.fuelhh_rows, snapshot.manifest)

    @property
    def issues(self) -> tuple[ForecastIssue, ...]:
        """All forecast issues, oldest first."""
        return self._issues

    def issues_covering(self, start: datetime, end: datetime) -> list[ForecastIssue]:
        """Issues with at least one point in ``[start, end)``, oldest first."""
        return issues_covering(self._issues, start, end)

    def actuals_between(self, start: datetime, end: datetime) -> list[ActualPoint]:
        """Half-hourly actuals with ``start <= target_time < end``."""
        lo = bisect_left(self._actual_times, start)
        hi = bisect_left(self._actual_times, end)
        return list(self._actuals[lo:hi])

    def hourly_actuals_between(
        self, start: datetime, end: datetime
    ) -> dict[datetime, HourlyActual]:
        """Hourly-mean actuals keyed by hour start for ``[start, end)``."""
        return hourly_mean(self.actuals_between(start, end))

    def extent(self) -> DataExtent:
        """Describe what is loaded (for the /meta endpoint and health checks)."""
        return DataExtent(
            first_issue_time=self._issues[0].issue_time if self._issues else None,
            last_issue_time=self._issues[-1].issue_time if self._issues else None,
            issue_count=len(self._issues),
            first_actual_time=self._actuals[0].target_time if self._actuals else None,
            last_actual_time=self._actuals[-1].target_time if self._actuals else None,
            actual_count=len(self._actuals),
        )
