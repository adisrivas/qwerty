"""Parse raw Elexon rows into domain objects. Malformed rows raise ``ParseError``."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from app.domain.models import ActualPoint, ForecastIssue, ForecastPoint

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

WIND_FUEL_TYPE = "WIND"


class ParseError(ValueError):
    """A row from Elexon could not be interpreted."""


def parse_timestamp(value: Any, *, field: str, index: int) -> datetime:
    """Parse an ISO-8601 timestamp (``2026-01-10T02:30:00Z``) into an aware UTC datetime."""
    if not isinstance(value, str) or not value:
        msg = f"row {index}: '{field}' must be a non-empty string, got {value!r}"
        raise ParseError(msg)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        msg = f"row {index}: '{field}' is not ISO-8601: {value!r}"
        raise ParseError(msg) from exc
    if parsed.tzinfo is None:
        msg = f"row {index}: '{field}' has no timezone: {value!r}"
        raise ParseError(msg)
    return parsed.astimezone(UTC)


def parse_generation(value: Any, *, index: int) -> float:
    """Parse a MW value; it must be a finite number."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        msg = f"row {index}: 'generation' must be numeric, got {value!r}"
        raise ParseError(msg)
    number = float(value)
    if not math.isfinite(number):
        msg = f"row {index}: 'generation' must be finite, got {value!r}"
        raise ParseError(msg)
    return number


def parse_forecast_rows(rows: Iterable[Mapping[str, Any]]) -> list[ForecastIssue]:
    """Group WINDFOR rows into issues (one per ``publishTime``), sorted by issue time.

    If the same ``(publishTime, startTime)`` appears more than once, the first occurrence
    wins. This happens when chunked downloads overlap at their boundaries.
    """
    seen: set[tuple[datetime, datetime]] = set()
    grouped: dict[datetime, list[ForecastPoint]] = defaultdict(list)

    for index, row in enumerate(rows):
        issue_time = parse_timestamp(row.get("publishTime"), field="publishTime", index=index)
        target_time = parse_timestamp(row.get("startTime"), field="startTime", index=index)
        key = (issue_time, target_time)
        if key in seen:
            continue
        seen.add(key)
        grouped[issue_time].append(
            ForecastPoint(
                issue_time=issue_time,
                target_time=target_time,
                generation_mw=parse_generation(row.get("generation"), index=index),
            )
        )

    return [
        ForecastIssue(
            issue_time=issue_time,
            points=tuple(sorted(points, key=lambda p: p.target_time)),
        )
        for issue_time, points in sorted(grouped.items())
    ]


def parse_actual_rows(
    rows: Iterable[Mapping[str, Any]], *, fuel_type: str = WIND_FUEL_TYPE
) -> list[ActualPoint]:
    """Parse FUELHH rows for one fuel type into actual points, sorted by target time.

    Rows for other fuel types are ignored (defence in depth: the client asks Elexon for
    WIND only, but a snapshot could have been produced differently). If a ``startTime``
    appears more than once, the row with the latest ``publishTime`` wins, because Elexon
    republishes corrected values.
    """
    best: dict[datetime, tuple[datetime, ActualPoint]] = {}

    for index, row in enumerate(rows):
        if row.get("fuelType") != fuel_type:
            continue
        target_time = parse_timestamp(row.get("startTime"), field="startTime", index=index)
        publish_time = parse_timestamp(row.get("publishTime"), field="publishTime", index=index)
        point = ActualPoint(
            target_time=target_time,
            generation_mw=parse_generation(row.get("generation"), index=index),
            settlement_date=_parse_date(row.get("settlementDate"), index=index),
            settlement_period=_parse_period(row.get("settlementPeriod"), index=index),
        )
        current = best.get(target_time)
        if current is None or publish_time > current[0]:
            best[target_time] = (publish_time, point)

    return [point for _, point in sorted(best.values(), key=lambda item: item[1].target_time)]


def _parse_date(value: Any, *, index: int) -> date:
    if not isinstance(value, str):
        msg = f"row {index}: 'settlementDate' must be a string, got {value!r}"
        raise ParseError(msg)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        msg = f"row {index}: 'settlementDate' is not yyyy-MM-dd: {value!r}"
        raise ParseError(msg) from exc


def _parse_period(value: Any, *, index: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 50:
        msg = f"row {index}: 'settlementPeriod' must be an integer 1-50, got {value!r}"
        raise ParseError(msg)
    return value
