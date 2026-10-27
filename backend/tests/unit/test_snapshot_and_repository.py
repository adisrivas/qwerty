from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from app.core.errors import SnapshotIntegrityError
from app.data.repository import WindDataRepository
from app.data.snapshot import (
    FUELHH_FILE,
    MANIFEST_FILE,
    default_fuelhh_params,
    default_windfor_params,
    load_snapshot,
    write_snapshot,
)
from tests.fixtures import synthetic


def _write(directory: Path) -> None:
    write_snapshot(
        directory,
        base_url="https://example.test",
        windfor_rows=synthetic.windfor_rows()[:146],
        windfor_params={"publishDateTimeFrom": "a", "publishDateTimeTo": "b"},
        fuelhh_rows=synthetic.fuelhh_rows()[:48],
        fuelhh_params={"settlementDateFrom": "c", "settlementDateTo": "d", "fuelType": "WIND"},
    )


def test_snapshot_roundtrip(tmp_path: Path) -> None:
    _write(tmp_path)
    snapshot = load_snapshot(tmp_path)
    assert snapshot.manifest.windfor.row_count == 146
    assert snapshot.manifest.fuelhh.row_count == 48
    assert len(snapshot.windfor_rows) == 146
    assert snapshot.manifest.created_at.tzinfo is not None


def test_snapshot_detects_tampering(tmp_path: Path) -> None:
    _write(tmp_path)
    path = tmp_path / FUELHH_FILE
    path.write_text(path.read_text().replace("WIND", "WINX", 1))
    with pytest.raises(SnapshotIntegrityError, match="checksum"):
        load_snapshot(tmp_path)


def test_snapshot_missing_manifest_or_file(tmp_path: Path) -> None:
    with pytest.raises(SnapshotIntegrityError, match="manifest"):
        load_snapshot(tmp_path)
    _write(tmp_path)
    (tmp_path / FUELHH_FILE).unlink()
    with pytest.raises(SnapshotIntegrityError, match="missing"):
        load_snapshot(tmp_path)


def test_snapshot_row_count_mismatch(tmp_path: Path) -> None:
    _write(tmp_path)
    manifest = (tmp_path / MANIFEST_FILE).read_text().replace('"row_count": 48', '"row_count": 47')
    (tmp_path / MANIFEST_FILE).write_text(manifest)
    with pytest.raises(SnapshotIntegrityError, match="expected 47 rows"):
        load_snapshot(tmp_path)


def test_default_params_cover_scope() -> None:
    wf = default_windfor_params(date(2026, 1, 1), date(2026, 1, 31))
    assert wf == {
        "publishDateTimeFrom": "2025-12-30T00:00:00Z",
        "publishDateTimeTo": "2026-02-03T00:00:00Z",
    }
    fh = default_fuelhh_params(date(2026, 1, 1), date(2026, 1, 31))
    assert fh == {
        "settlementDateFrom": "2026-01-01",
        "settlementDateTo": "2026-02-01",
        "fuelType": "WIND",
    }
    # With 16 days of history for calibration and the persistence baseline.
    assert (
        default_windfor_params(date(2026, 1, 1), date(2026, 1, 31), 16)["publishDateTimeFrom"]
        == "2025-12-14T00:00:00Z"
    )
    assert (
        default_fuelhh_params(date(2026, 1, 1), date(2026, 1, 31), 16)["settlementDateFrom"]
        == "2025-12-16"
    )


def test_repository_window_queries(synthetic_repo: WindDataRepository) -> None:
    start = datetime(2026, 1, 11, 0, 0, tzinfo=UTC)
    end = start + timedelta(days=1)
    actuals = synthetic_repo.actuals_between(start, end)
    assert len(actuals) == 48
    assert actuals[0].target_time == start
    assert actuals[-1].target_time == end - timedelta(minutes=30)  # end is exclusive

    hourly = synthetic_repo.hourly_actuals_between(start, end)
    assert len(hourly) == 24
    assert all(h.is_complete for h in hourly.values())

    covering = synthetic_repo.issues_covering(start, end)
    # From the 9 Jan 02:30 issue (covers up to 21:00 on 11 Jan) to the last issue of
    # 12 Jan (every 12 Jan issue starts at 21:00 on 11 Jan, so all eight cover 3 hours).
    assert covering[0].issue_time == datetime(2026, 1, 9, 2, 30, tzinfo=UTC)
    assert covering[-1].issue_time == datetime(2026, 1, 12, 22, 30, tzinfo=UTC)
    assert len(covering) == 8 + 8 + 8 + 8  # 9, 10, 11 and 12 Jan issues

    extent = synthetic_repo.extent()
    assert extent.issue_count == 64
    assert extent.actual_count == 239  # 5 days * 48 minus the one deliberate gap


def test_empty_repository_extent() -> None:
    extent = WindDataRepository([], []).extent()
    assert extent.issue_count == 0
    assert extent.first_issue_time is None
    assert extent.last_actual_time is None
