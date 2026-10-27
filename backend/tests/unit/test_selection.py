from datetime import UTC, date, datetime, time

import pytest

from app.domain.models import ForecastIssue, ForecastPoint
from app.domain.selection import (
    cutoff_instant_utc,
    delivery_date_for,
    issue_slot_label,
    issues_covering,
    local_day_window_utc,
    select_as_of_issue,
)


def _issue(issue_time: datetime, first_target: datetime, hours: int = 3) -> ForecastIssue:
    points = tuple(
        ForecastPoint(
            issue_time=issue_time,
            target_time=first_target.replace(hour=first_target.hour)
            + i * (datetime(2000, 1, 1, 1, tzinfo=UTC) - datetime(2000, 1, 1, 0, tzinfo=UTC)),
            generation_mw=1.0,
        )
        for i in range(hours)
    )
    return ForecastIssue(issue_time=issue_time, points=points)


def test_delivery_date_is_the_next_day() -> None:
    assert delivery_date_for(date(2026, 1, 31)) == date(2026, 2, 1)


def test_january_day_window_is_24_hours_utc() -> None:
    start, end = local_day_window_utc(date(2026, 1, 15))
    assert start == datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
    assert end == datetime(2026, 1, 16, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("day", "hours"),
    [(date(2026, 3, 29), 23), (date(2026, 10, 25), 25), (date(2026, 7, 1), 24)],
)
def test_day_window_handles_daylight_saving(day: date, hours: int) -> None:
    start, end = local_day_window_utc(day)
    assert (end - start).total_seconds() == hours * 3600


def test_cutoff_instant_winter_and_summer() -> None:
    assert cutoff_instant_utc(date(2026, 1, 10), time(9, 50)) == datetime(
        2026, 1, 10, 9, 50, tzinfo=UTC
    )
    # British Summer Time: 09:50 local is 08:50 UTC.
    assert cutoff_instant_utc(date(2026, 7, 10), time(9, 50)) == datetime(
        2026, 7, 10, 8, 50, tzinfo=UTC
    )


def test_select_as_of_picks_latest_not_after_cutoff() -> None:
    t0 = datetime(2026, 1, 10, 0, 0, tzinfo=UTC)
    early = _issue(datetime(2026, 1, 10, 7, 30, tzinfo=UTC), t0)
    on_time = _issue(datetime(2026, 1, 10, 9, 50, tzinfo=UTC), t0)
    late = _issue(datetime(2026, 1, 10, 9, 51, tzinfo=UTC), t0)
    cutoff = datetime(2026, 1, 10, 9, 50, tzinfo=UTC)

    assert select_as_of_issue([late, early, on_time], cutoff) is on_time
    assert select_as_of_issue([late], cutoff) is None
    assert select_as_of_issue([], cutoff) is None


def test_issues_covering_uses_half_open_window() -> None:
    issue = _issue(
        datetime(2026, 1, 9, 2, 30, tzinfo=UTC), datetime(2026, 1, 9, 21, 0, tzinfo=UTC), hours=3
    )  # covers 21:00, 22:00, 23:00 on 9 Jan
    day_start = datetime(2026, 1, 10, 0, 0, tzinfo=UTC)
    day_end = datetime(2026, 1, 11, 0, 0, tzinfo=UTC)
    assert issues_covering([issue], day_start, day_end) == []
    assert issues_covering([issue], datetime(2026, 1, 9, 23, 0, tzinfo=UTC), day_start) == [issue]
    assert issues_covering([issue], datetime(2026, 1, 9, 0, 0, tzinfo=UTC), day_start) == [issue]


def test_issue_slot_label_is_local_wall_clock() -> None:
    assert issue_slot_label(datetime(2026, 1, 10, 9, 30, tzinfo=UTC)) == "09:30"
    assert issue_slot_label(datetime(2026, 7, 10, 9, 30, tzinfo=UTC)) == "10:30"
