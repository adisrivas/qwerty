from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.data.repository import WindDataRepository
from app.data.snapshot import write_snapshot
from app.main import create_app
from tests.fixtures import synthetic

COMMITTED_SNAPSHOT = Path(__file__).resolve().parents[1] / "data" / "snapshots"


@pytest.fixture(scope="session")
def synthetic_snapshot_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("snapshot")
    write_snapshot(
        directory,
        base_url="https://example.test/api",
        windfor_rows=synthetic.windfor_rows(),
        windfor_params={"publishDateTimeFrom": "x", "publishDateTimeTo": "y"},
        fuelhh_rows=synthetic.fuelhh_rows(),
        fuelhh_params={"settlementDateFrom": "a", "settlementDateTo": "b", "fuelType": "WIND"},
        notes=["synthetic"],
        created_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    return directory


@pytest.fixture(scope="session")
def synthetic_settings(synthetic_snapshot_dir: Path) -> Settings:
    return Settings(
        environment="test",
        snapshot_dir=synthetic_snapshot_dir,
        first_decision_date=synthetic.FIRST_DECISION,
        last_decision_date=synthetic.LAST_DECISION,
        log_level="WARNING",
    )


@pytest.fixture(scope="session")
def synthetic_repo(synthetic_snapshot_dir: Path) -> WindDataRepository:
    return WindDataRepository.from_snapshot(synthetic_snapshot_dir)


@pytest.fixture
def client(synthetic_settings: Settings) -> Iterator[TestClient]:
    app = create_app(synthetic_settings)
    app.dependency_overrides[get_settings] = lambda: synthetic_settings
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def committed_repo() -> WindDataRepository:
    if not (COMMITTED_SNAPSHOT / "manifest.json").exists():
        pytest.skip("committed snapshot not present")
    return WindDataRepository.from_snapshot(COMMITTED_SNAPSHOT)
