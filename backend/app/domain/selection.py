"""Select the forecast issue available at the decision cutoff.

Only issues published at or before the cutoff are eligible; the latest of them is used.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from app.domain.models import ForecastIssue

UK_TZ = ZoneInfo("Europe/London")


def delivery_date_for(decision_date: date) -> date:
    """The day-ahead market trades power for the calendar day after the decision day."""
    return decision_date + timedelta(days=1)


def local_day_window_utc(day: date, tz: ZoneInfo = UK_TZ) -> tuple[datetime, datetime]:
    """Return ``(start, end)`` in UTC for the local calendar day ``day``.

    ``end`` is exclusive. In January the UK is on GMT so the window is 00:00 to 24:00 UTC,
    but the function is written for any date so that daylight-saving days are handled
    correctly (they are 23 or 25 hours long).
    """
    start_local = datetime.combine(day, time.min, tzinfo=tz)
    end_local = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def cutoff_instant_utc(decision_date: date, cutoff: time, tz: ZoneInfo = UK_TZ) -> datetime:
    """Convert a local-time cutoff on the decision day into an absolute UTC instant."""
    return datetime.combine(decision_date, cutoff, tzinfo=tz).astimezone(UTC)


def issues_covering(
    issues: Iterable[ForecastIssue], window_start: datetime, window_end: datetime
) -> list[ForecastIssue]:
    """Issues that contain at least one point inside ``[window_start, window_end)``."""
    return [
        issue
        for issue in issues
        if issue.first_target < window_end and issue.last_target >= window_start
    ]


def select_as_of_issue(
    issues: Sequence[ForecastIssue], cutoff_utc: datetime
) -> ForecastIssue | None:
    """Pick the latest issue published at or before ``cutoff_utc``.

    Returns ``None`` when nothing qualifies. There is deliberately no fallback to a later
    issue: using information published after the auction closed would overstate what the
    desk could have known.
    """
    eligible = [issue for issue in issues if issue.issue_time <= cutoff_utc]
    if not eligible:
        return None
    return max(eligible, key=lambda issue: issue.issue_time)


def issue_slot_label(issue_time: datetime, tz: ZoneInfo = UK_TZ) -> str:
    """Local wall-clock label such as ``"09:30"`` used to group issues by publication slot."""
    return issue_time.astimezone(tz).strftime("%H:%M")
