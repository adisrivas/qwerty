"""Fetch the January 2026 data from Elexon and (re)write the committed snapshot.

Usage (from the ``backend`` directory)::

    uv run python -m scripts.refresh_snapshot            # defaults from settings
    uv run python -m scripts.refresh_snapshot --out /tmp/snap

The script is the only place in the code base that talks to Elexon in normal use. It
prints a short summary and exits non-zero on any failure, so it is safe to run in CI.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.data.elexon_client import ElexonApiError, ElexonClient
from app.data.parsers import ParseError, parse_actual_rows, parse_forecast_rows
from app.data.snapshot import default_fuelhh_params, default_windfor_params, write_snapshot

log = logging.getLogger("refresh_snapshot")

NOTES = [
    "WINDFOR is NESO's national wind generation forecast for transmission-connected wind "
    "(Power Park Modules), hourly, published several times a day.",
    "FUELHH fuelType=WIND is the measured half-hourly average MW of transmission-metered wind. "
    "Embedded (distribution-connected) wind is not included in either dataset.",
    "Actual generation includes the effect of curtailment instructed by the system operator, "
    "which the forecast does not model; part of any forecast-minus-actual gap is operational.",
]


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    settings = get_settings()
    configure_logging(settings.log_level)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=settings.snapshot_dir)
    parser.add_argument(
        "--first-decision", type=date.fromisoformat, default=settings.first_decision_date
    )
    parser.add_argument(
        "--last-decision", type=date.fromisoformat, default=settings.last_decision_date
    )
    args = parser.parse_args(argv)

    history_days = settings.calibration_lookback_days + 2
    windfor_params = default_windfor_params(args.first_decision, args.last_decision, history_days)
    fuelhh_params = default_fuelhh_params(args.first_decision, args.last_decision, history_days)

    try:
        with ElexonClient(
            settings.elexon_base_url,
            timeout_seconds=settings.elexon_timeout_seconds,
            max_retries=settings.elexon_max_retries,
        ) as client:
            windfor_rows = client.fetch_windfor(
                datetime.fromisoformat(
                    windfor_params["publishDateTimeFrom"].replace("Z", "+00:00")
                ),
                datetime.fromisoformat(windfor_params["publishDateTimeTo"].replace("Z", "+00:00")),
            )
            fuelhh_rows = client.fetch_fuelhh(
                date.fromisoformat(fuelhh_params["settlementDateFrom"]),
                date.fromisoformat(fuelhh_params["settlementDateTo"]),
                fuel_type=fuelhh_params["fuelType"],
            )
        issues = parse_forecast_rows(windfor_rows)
        actuals = parse_actual_rows(fuelhh_rows)
    except (ElexonApiError, ParseError) as exc:
        log.error("refresh failed", extra={"ctx_error": str(exc)})
        return 1

    manifest = write_snapshot(
        args.out,
        base_url=settings.elexon_base_url,
        windfor_rows=windfor_rows,
        windfor_params=windfor_params,
        fuelhh_rows=fuelhh_rows,
        fuelhh_params=fuelhh_params,
        notes=NOTES,
        created_at=datetime.now(UTC),
    )
    log.info(
        "snapshot written",
        extra={
            "ctx_dir": str(args.out),
            "ctx_windfor_rows": manifest.windfor.row_count,
            "ctx_windfor_issues": len(issues),
            "ctx_fuelhh_rows": manifest.fuelhh.row_count,
            "ctx_fuelhh_points": len(actuals),
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
