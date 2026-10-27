"""A small synthetic Elexon dataset with known answers.

Shape mirrors the real feeds exactly (field names, 73-hour issues, 8 daily slots, half-hourly
actuals) but the numbers are constructed so every expected result can be derived by hand:

* Actual generation for hour ``t`` is ``BASE(t)``, identical in both half-hours, so the
  hourly mean equals ``BASE(t)``.
* An issue published at slot index ``i`` (0 = 02:30 ... 7 = 22:30) forecasts
  ``BASE(t) + SLOT_BIAS[i]`` for every hour. The error of that issue is therefore exactly
  ``SLOT_BIAS[i]`` for every hour of every day.

Quirks deliberately included:

* On ``LATE_DAY`` the 09:30 issue was published late, at 12:25. The as-of selection at a
  09:50 cutoff must therefore fall back to the 07:30 issue (bias 800).
* On ``GAP_DELIVERY_DAY`` the half-hour starting 02:30 is missing, so hour 02:00 is
  incomplete and must be excluded from metrics (23 pairs instead of 24).
* Actuals start two days before the first delivery day so the 48-hour persistence
  baseline exists. Because ``BASE`` rises by 10 MW per calendar day, persistence is low by
  exactly 20 MW every hour (error -20).
* Only three decision days have forecast history, fewer than the calibration minimum, so
  no uncertainty band is produced for the synthetic data.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

SLOT_TIMES = [
    time(2, 30),
    time(4, 30),
    time(7, 30),
    time(9, 30),
    time(11, 30),
    time(15, 30),
    time(18, 30),
    time(22, 30),
]
SLOT_BIAS = [1000.0, 900.0, 800.0, 700.0, 600.0, 500.0, 400.0, 300.0]
AS_OF_0950_SLOT = 3  # 09:30 -> bias 700
FALLBACK_SLOT = 2  # 07:30 -> bias 800

FIRST_DECISION = date(2026, 1, 10)
LAST_DECISION = date(2026, 1, 12)
LATE_DAY = date(2026, 1, 11)  # decision day whose 09:30 issue came out at 12:25
GAP_DELIVERY_DAY = date(2026, 1, 13)  # delivery day with a missing half-hour at 02:30
GAP_HOUR = 2

ISSUE_DAYS = [date(2026, 1, 8) + timedelta(days=i) for i in range(8)]  # 8 Jan .. 15 Jan
ACTUAL_DAYS = [date(2026, 1, 9) + timedelta(days=i) for i in range(5)]  # 9 Jan .. 13 Jan


def base_mw(moment: datetime) -> float:
    """Smooth, strictly positive 'true' wind profile that depends only on the hour."""
    return 8000.0 + 200.0 * moment.hour + 10.0 * moment.day


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def windfor_rows() -> list[dict[str, Any]]:
    """WINDFOR-shaped rows for every slot of every issue day."""
    rows: list[dict[str, Any]] = []
    for day in ISSUE_DAYS:
        for slot_index, slot_time in enumerate(SLOT_TIMES):
            publish = datetime.combine(day, slot_time, tzinfo=UTC)
            if day == LATE_DAY and slot_index == AS_OF_0950_SLOT:
                publish = datetime.combine(day, time(12, 25), tzinfo=UTC)
            first_target = datetime.combine(day - timedelta(days=1), time(21, 0), tzinfo=UTC)
            for hour in range(73):
                target = first_target + timedelta(hours=hour)
                rows.append(
                    {
                        "dataset": "WINDFOR",
                        "publishTime": _iso(publish),
                        "startTime": _iso(target),
                        "generation": base_mw(target) + SLOT_BIAS[slot_index],
                    }
                )
    return rows


def fuelhh_rows() -> list[dict[str, Any]]:
    """FUELHH-shaped WIND rows for the delivery days, with one half-hour missing."""
    rows: list[dict[str, Any]] = []
    for day in ACTUAL_DAYS:
        for period in range(1, 49):
            start = datetime.combine(day, time.min, tzinfo=UTC) + timedelta(
                minutes=30 * (period - 1)
            )
            if day == GAP_DELIVERY_DAY and start.hour == GAP_HOUR and start.minute == 30:
                continue
            rows.append(
                {
                    "dataset": "FUELHH",
                    "publishTime": _iso(start + timedelta(minutes=30)),
                    "startTime": _iso(start),
                    "settlementDate": day.isoformat(),
                    "settlementPeriod": period,
                    "fuelType": "WIND",
                    "generation": base_mw(start.replace(minute=0)),
                }
            )
    return rows
