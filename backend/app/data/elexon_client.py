"""HTTP client for the Elexon Insights ``/datasets/*/stream`` endpoints.

Requests are chunked by date window and retried with back-off on transient failures.
Client errors are not retried and carry Elexon's message. Rows are returned unparsed.
"""

from __future__ import annotations

import logging
import random
import time
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from collections.abc import Iterator

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
JsonRows = list[dict[str, Any]]


class ElexonApiError(RuntimeError):
    """Elexon rejected the request or returned something we cannot use."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ElexonClient:
    """Small, explicit wrapper around the two datasets this product uses."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
        sleep: Any = time.sleep,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
            headers={"Accept": "application/json", "User-Agent": "day-ahead-wind-forecast/0.1"},
        )
        self._max_retries = max_retries
        self._sleep = sleep

    def close(self) -> None:
        """Release the underlying connection pool."""
        self._client.close()

    def __enter__(self) -> ElexonClient:
        """Support ``with ElexonClient(...) as client``."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Close on context exit."""
        self.close()

    def fetch_windfor(
        self, publish_from: datetime, publish_to: datetime, *, chunk_days: int = 7
    ) -> JsonRows:
        """All WINDFOR rows published in ``[publish_from, publish_to]``."""
        rows: JsonRows = []
        for start, end in _datetime_chunks(publish_from, publish_to, chunk_days):
            rows.extend(
                self._get_rows(
                    "/datasets/WINDFOR/stream",
                    {"publishDateTimeFrom": _iso(start), "publishDateTimeTo": _iso(end)},
                )
            )
        return rows

    def fetch_fuelhh(
        self,
        settlement_from: date,
        settlement_to: date,
        *,
        fuel_type: str = "WIND",
        chunk_days: int = 7,
    ) -> JsonRows:
        """All FUELHH rows for one fuel type with settlement dates in the inclusive range."""
        rows: JsonRows = []
        for start, end in _date_chunks(settlement_from, settlement_to, chunk_days):
            rows.extend(
                self._get_rows(
                    "/datasets/FUELHH/stream",
                    {
                        "settlementDateFrom": start.isoformat(),
                        "settlementDateTo": end.isoformat(),
                        "fuelType": fuel_type,
                    },
                )
            )
        return rows

    def _get_rows(self, path: str, params: dict[str, str]) -> JsonRows:
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._client.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt > self._max_retries:
                    msg = f"Elexon unreachable after {attempt - 1} retries: {exc}"
                    raise ElexonApiError(msg) from exc
                self._backoff(attempt, reason=str(exc))
                continue

            if response.status_code in RETRYABLE_STATUS and attempt <= self._max_retries:
                self._backoff(attempt, reason=f"HTTP {response.status_code}")
                continue
            if response.status_code >= 400:
                raise ElexonApiError(_describe_error(response), status_code=response.status_code)

            payload = response.json()
            if not isinstance(payload, list):
                msg = f"Expected a JSON array from {path}, got {type(payload).__name__}"
                raise ElexonApiError(msg, status_code=response.status_code)
            log.info(
                "elexon fetch ok",
                extra={"ctx_path": path, "ctx_params": params, "ctx_rows": len(payload)},
            )
            return payload

    def _backoff(self, attempt: int, *, reason: str) -> None:
        delay = min(2 ** (attempt - 1), 8) + random.uniform(0, 0.5)
        log.warning(
            "elexon retry",
            extra={"ctx_attempt": attempt, "ctx_delay_s": round(delay, 2), "ctx_reason": reason},
        )
        self._sleep(delay)


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _describe_error(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"Elexon returned HTTP {response.status_code}"
    if isinstance(body, dict):
        errors = body.get("errors")
        title = body.get("title", "error")
        if isinstance(errors, dict):
            details = "; ".join(f"{k}: {', '.join(map(str, v))}" for k, v in errors.items())
            return f"Elexon returned HTTP {response.status_code}: {title} ({details})"
        return f"Elexon returned HTTP {response.status_code}: {title}"
    return f"Elexon returned HTTP {response.status_code}"


def _datetime_chunks(
    start: datetime, end: datetime, chunk_days: int
) -> Iterator[tuple[datetime, datetime]]:
    if end < start:
        msg = "publish_to must not be before publish_from"
        raise ValueError(msg)
    step = timedelta(days=chunk_days)
    cursor = start
    while cursor < end:
        nxt = min(cursor + step, end)
        yield cursor, nxt
        cursor = nxt
    if start == end:
        yield start, end


def _date_chunks(start: date, end: date, chunk_days: int) -> Iterator[tuple[date, date]]:
    if end < start:
        msg = "settlement_to must not be before settlement_from"
        raise ValueError(msg)
    cursor = start
    while cursor <= end:
        nxt = min(cursor + timedelta(days=chunk_days - 1), end)
        yield cursor, nxt
        cursor = nxt + timedelta(days=1)
