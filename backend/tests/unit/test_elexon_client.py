import itertools
from datetime import UTC, date, datetime

import httpx
import pytest
import respx

from app.data.elexon_client import ElexonApiError, ElexonClient, _date_chunks, _datetime_chunks

BASE = "https://elexon.test/api/v1"


def _client(**kwargs: object) -> ElexonClient:
    return ElexonClient(BASE, max_retries=2, sleep=lambda _s: None, **kwargs)  # type: ignore[arg-type]


def test_datetime_chunks_cover_range_without_gaps() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 20, tzinfo=UTC)
    chunks = list(_datetime_chunks(start, end, 7))
    assert chunks[0][0] == start
    assert chunks[-1][1] == end
    assert all(a[1] == b[0] for a, b in itertools.pairwise(chunks))
    assert list(_datetime_chunks(start, start, 7)) == [(start, start)]
    with pytest.raises(ValueError, match="before"):
        list(_datetime_chunks(end, start, 7))


def test_date_chunks_are_inclusive_and_contiguous() -> None:
    chunks = list(_date_chunks(date(2026, 1, 1), date(2026, 1, 10), 4))
    assert chunks == [
        (date(2026, 1, 1), date(2026, 1, 4)),
        (date(2026, 1, 5), date(2026, 1, 8)),
        (date(2026, 1, 9), date(2026, 1, 10)),
    ]
    with pytest.raises(ValueError, match="before"):
        list(_date_chunks(date(2026, 1, 2), date(2026, 1, 1), 4))


@respx.mock
def test_fetch_windfor_chunks_and_concatenates() -> None:
    route = respx.get(f"{BASE}/datasets/WINDFOR/stream").mock(
        side_effect=[httpx.Response(200, json=[{"a": 1}]), httpx.Response(200, json=[{"a": 2}])]
    )
    with _client() as client:
        rows = client.fetch_windfor(
            datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 10, tzinfo=UTC), chunk_days=7
        )
    assert rows == [{"a": 1}, {"a": 2}]
    assert route.call_count == 2
    first_params = route.calls[0].request.url.params
    assert first_params["publishDateTimeFrom"] == "2026-01-01T00:00:00Z"
    assert first_params["publishDateTimeTo"] == "2026-01-08T00:00:00Z"


@respx.mock
def test_fetch_fuelhh_passes_fuel_type_and_settlement_dates() -> None:
    route = respx.get(f"{BASE}/datasets/FUELHH/stream").mock(
        return_value=httpx.Response(200, json=[])
    )
    with _client() as client:
        client.fetch_fuelhh(date(2026, 1, 1), date(2026, 1, 3), chunk_days=7)
    params = route.calls[0].request.url.params
    assert params["fuelType"] == "WIND"
    assert params["settlementDateFrom"] == "2026-01-01"
    assert params["settlementDateTo"] == "2026-01-03"


@respx.mock
def test_retries_on_503_then_succeeds() -> None:
    route = respx.get(f"{BASE}/datasets/WINDFOR/stream").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=[{"ok": True}])]
    )
    with _client() as client:
        rows = client.fetch_windfor(
            datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC)
        )
    assert rows == [{"ok": True}]
    assert route.call_count == 2


@respx.mock
def test_gives_up_after_max_retries_on_5xx() -> None:
    respx.get(f"{BASE}/datasets/WINDFOR/stream").mock(return_value=httpx.Response(502))
    with _client() as client, pytest.raises(ElexonApiError) as info:
        client.fetch_windfor(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC))
    assert info.value.status_code == 502


@respx.mock
def test_4xx_is_not_retried_and_surfaces_elexon_message() -> None:
    route = respx.get(f"{BASE}/datasets/WINDFOR/stream").mock(
        return_value=httpx.Response(
            400,
            json={
                "title": "One or more validation errors occurred.",
                "errors": {"PublishDateTimeFrom": ["DateTime should be in ISO format"]},
            },
        )
    )
    with _client() as client, pytest.raises(ElexonApiError, match="ISO format"):
        client.fetch_windfor(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC))
    assert route.call_count == 1


@respx.mock
def test_non_json_4xx_and_non_list_payload() -> None:
    respx.get(f"{BASE}/datasets/FUELHH/stream").mock(return_value=httpx.Response(404, text="nope"))
    with _client() as client, pytest.raises(ElexonApiError, match="HTTP 404"):
        client.fetch_fuelhh(date(2026, 1, 1), date(2026, 1, 1))

    respx.get(f"{BASE}/datasets/WINDFOR/stream").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    with _client() as client, pytest.raises(ElexonApiError, match="JSON array"):
        client.fetch_windfor(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC))


@respx.mock
def test_transport_errors_are_retried_then_raised() -> None:
    route = respx.get(f"{BASE}/datasets/WINDFOR/stream").mock(
        side_effect=httpx.ConnectError("boom")
    )
    with _client() as client, pytest.raises(ElexonApiError, match="unreachable"):
        client.fetch_windfor(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC))
    assert route.call_count == 3  # 1 attempt + 2 retries
