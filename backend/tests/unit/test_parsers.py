from datetime import UTC, date, datetime

import pytest

from app.data.parsers import (
    ParseError,
    parse_actual_rows,
    parse_forecast_rows,
    parse_generation,
    parse_timestamp,
)


def _wf(publish: str, start: str, mw: float) -> dict[str, object]:
    return {"dataset": "WINDFOR", "publishTime": publish, "startTime": start, "generation": mw}


def _fh(
    publish: str, start: str, mw: float, fuel: str = "WIND", period: int = 1
) -> dict[str, object]:
    return {
        "dataset": "FUELHH",
        "publishTime": publish,
        "startTime": start,
        "settlementDate": start[:10],
        "settlementPeriod": period,
        "fuelType": fuel,
        "generation": mw,
    }


def test_parse_timestamp_accepts_z_and_offsets() -> None:
    assert parse_timestamp("2026-01-10T02:30:00Z", field="x", index=0) == datetime(
        2026, 1, 10, 2, 30, tzinfo=UTC
    )
    assert parse_timestamp("2026-01-10T03:30:00+01:00", field="x", index=0) == datetime(
        2026, 1, 10, 2, 30, tzinfo=UTC
    )


@pytest.mark.parametrize("bad", ["", None, "2026-01-10T02:30:00", "yesterday", 42])
def test_parse_timestamp_rejects_bad_values(bad: object) -> None:
    with pytest.raises(ParseError):
        parse_timestamp(bad, field="startTime", index=3)


@pytest.mark.parametrize("bad", ["12", True, None, float("nan"), float("inf")])
def test_parse_generation_rejects_bad_values(bad: object) -> None:
    with pytest.raises(ParseError):
        parse_generation(bad, index=0)


def test_forecast_rows_group_sort_and_dedupe() -> None:
    rows = [
        _wf("2026-01-10T04:30:00Z", "2026-01-10T01:00:00Z", 20.0),
        _wf("2026-01-10T02:30:00Z", "2026-01-10T01:00:00Z", 11.0),
        _wf("2026-01-10T02:30:00Z", "2026-01-10T00:00:00Z", 10.0),
        _wf("2026-01-10T02:30:00Z", "2026-01-10T01:00:00Z", 999.0),  # duplicate key: ignored
    ]
    issues = parse_forecast_rows(rows)
    assert [i.issue_time for i in issues] == [
        datetime(2026, 1, 10, 2, 30, tzinfo=UTC),
        datetime(2026, 1, 10, 4, 30, tzinfo=UTC),
    ]
    first = issues[0]
    assert [p.generation_mw for p in first.points] == [10.0, 11.0]
    assert first.first_target == datetime(2026, 1, 10, 0, 0, tzinfo=UTC)
    assert first.last_target == datetime(2026, 1, 10, 1, 0, tzinfo=UTC)
    assert len(first.points_between(first.first_target, first.last_target)) == 1


def test_actual_rows_filter_fuel_type_and_keep_latest_publication() -> None:
    rows = [
        _fh("2026-01-10T00:30:00Z", "2026-01-10T00:00:00Z", 100.0),
        _fh("2026-01-10T00:30:00Z", "2026-01-10T00:00:00Z", 5.0, fuel="CCGT"),
        _fh("2026-01-10T01:00:00Z", "2026-01-10T00:00:00Z", 120.0),  # corrected later
        _fh("2026-01-10T00:30:00Z", "2026-01-09T23:30:00Z", 90.0, period=48),
    ]
    actuals = parse_actual_rows(rows)
    assert [a.generation_mw for a in actuals] == [90.0, 120.0]
    assert actuals[1].settlement_date == date(2026, 1, 10)
    assert actuals[0].settlement_period == 48


@pytest.mark.parametrize(
    "mutation",
    [
        {"settlementDate": "10/01/2026"},
        {"settlementDate": None},
        {"settlementPeriod": 0},
        {"settlementPeriod": "1"},
        {"settlementPeriod": True},
    ],
)
def test_actual_rows_reject_bad_settlement_fields(mutation: dict[str, object]) -> None:
    row = _fh("2026-01-10T00:30:00Z", "2026-01-10T00:00:00Z", 1.0)
    row.update(mutation)
    with pytest.raises(ParseError):
        parse_actual_rows([row])
