"""Committed data snapshot: raw Elexon rows plus a manifest with parameters and SHA-256s.

The running application reads only the snapshot, which makes it fast, deterministic and
independent of Elexon availability.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.errors import SnapshotIntegrityError

MANIFEST_FILE = "manifest.json"
WINDFOR_FILE = "windfor.json"
FUELHH_FILE = "fuelhh_wind.json"


class FileRecord(BaseModel):
    """Provenance for one data file in the snapshot."""

    file: str
    row_count: int
    sha256: str
    endpoint: str
    params: dict[str, str]


class SnapshotManifest(BaseModel):
    """Everything needed to say exactly where the numbers in the app came from."""

    schema_version: int = 1
    created_at: datetime
    source_base_url: str
    windfor: FileRecord
    fuelhh: FileRecord
    notes: list[str] = Field(default_factory=list)


class Snapshot(BaseModel):
    """Loaded snapshot: the manifest plus the raw rows."""

    manifest: SnapshotManifest
    windfor_rows: list[dict[str, Any]]
    fuelhh_rows: list[dict[str, Any]]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _dump_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(rows, separators=(",", ":"), sort_keys=True), encoding="utf-8")


def write_snapshot(
    directory: Path,
    *,
    base_url: str,
    windfor_rows: list[dict[str, Any]],
    windfor_params: dict[str, str],
    fuelhh_rows: list[dict[str, Any]],
    fuelhh_params: dict[str, str],
    notes: list[str] | None = None,
    created_at: datetime | None = None,
) -> SnapshotManifest:
    """Write both data files and the manifest. Returns the manifest."""
    directory.mkdir(parents=True, exist_ok=True)
    windfor_path = directory / WINDFOR_FILE
    fuelhh_path = directory / FUELHH_FILE
    _dump_rows(windfor_path, windfor_rows)
    _dump_rows(fuelhh_path, fuelhh_rows)

    manifest = SnapshotManifest(
        created_at=created_at or datetime.now(UTC),
        source_base_url=base_url,
        windfor=FileRecord(
            file=WINDFOR_FILE,
            row_count=len(windfor_rows),
            sha256=_sha256(windfor_path),
            endpoint="/datasets/WINDFOR/stream",
            params=windfor_params,
        ),
        fuelhh=FileRecord(
            file=FUELHH_FILE,
            row_count=len(fuelhh_rows),
            sha256=_sha256(fuelhh_path),
            endpoint="/datasets/FUELHH/stream",
            params=fuelhh_params,
        ),
        notes=notes or [],
    )
    (directory / MANIFEST_FILE).write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def load_snapshot(directory: Path) -> Snapshot:
    """Read and verify a snapshot. Raises ``SnapshotIntegrityError`` on any mismatch."""
    manifest_path = directory / MANIFEST_FILE
    if not manifest_path.exists():
        msg = f"No snapshot manifest at {manifest_path}"
        raise SnapshotIntegrityError(msg)
    manifest = SnapshotManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    windfor_rows = _load_verified(directory, manifest.windfor)
    fuelhh_rows = _load_verified(directory, manifest.fuelhh)
    return Snapshot(manifest=manifest, windfor_rows=windfor_rows, fuelhh_rows=fuelhh_rows)


def _load_verified(directory: Path, record: FileRecord) -> list[dict[str, Any]]:
    path = directory / record.file
    if not path.exists():
        msg = f"Snapshot file missing: {path}"
        raise SnapshotIntegrityError(msg)
    actual_hash = _sha256(path)
    if actual_hash != record.sha256:
        msg = (
            f"{record.file}: checksum mismatch "
            f"(manifest {record.sha256[:12]}, file {actual_hash[:12]})"
        )
        raise SnapshotIntegrityError(msg)
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or len(rows) != record.row_count:
        msg = f"{record.file}: expected {record.row_count} rows"
        raise SnapshotIntegrityError(msg)
    return rows


def default_windfor_params(
    first_decision: date, last_decision: date, history_days: int = 0
) -> dict[str, str]:
    """Publish window wide enough for every delivery day plus ``history_days`` of context.

    Issues published the day before a decision day already cover its delivery day, so the
    window starts ``history_days + 2`` days before the first decision (one day of slack).
    Issues up to two days after the last delivery day still cover its final hours. The
    history is what lets the app calibrate early-January decisions on December errors
    without looking into the future.
    """
    from datetime import timedelta  # noqa: PLC0415  (local import keeps module header small)

    start = datetime.combine(
        first_decision - timedelta(days=history_days + 2), datetime.min.time(), tzinfo=UTC
    )
    end = datetime.combine(last_decision + timedelta(days=3), datetime.min.time(), tzinfo=UTC)
    return {
        "publishDateTimeFrom": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "publishDateTimeTo": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def default_fuelhh_params(
    first_decision: date, last_decision: date, history_days: int = 0
) -> dict[str, str]:
    """Settlement dates for every delivery day (decision day + 1) plus history.

    The history also covers the persistence baseline, which needs the actual from two days
    before each delivery day.
    """
    from datetime import timedelta  # noqa: PLC0415

    return {
        "settlementDateFrom": (first_decision - timedelta(days=history_days)).isoformat(),
        "settlementDateTo": (last_decision + timedelta(days=1)).isoformat(),
        "fuelType": "WIND",
    }
