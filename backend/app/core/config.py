"""Application settings.

Every tunable lives here and can be overridden with an environment variable prefixed
``WINDFORECAST_`` (for example ``WINDFORECAST_DEFAULT_CUTOFF=09:20``). Nothing else in the code
base hard-codes a date, time or URL.
"""

from __future__ import annotations

from datetime import date, time
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration with documented defaults."""

    model_config = SettingsConfigDict(env_prefix="WINDFORECAST_", env_file=".env", extra="ignore")

    app_name: str = "Day-ahead Wind Forecast"
    environment: str = Field(default="local", description="local | docker | vercel | test")
    log_level: str = "INFO"

    first_decision_date: date = date(2026, 1, 1)
    last_decision_date: date = date(2026, 1, 31)

    # N2EX GB day-ahead gate closure, UK local time.
    default_cutoff: time = time(9, 50)

    # Calibration window: delivery days completed before the decision day.
    calibration_lookback_days: int = 14
    calibration_min_days: int = 5

    # Persistence baseline: metered outturn this many hours earlier.
    persistence_lag_hours: int = 48

    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"
    elexon_timeout_seconds: float = 30.0
    elexon_max_retries: int = 3

    snapshot_dir: Path = BACKEND_ROOT / "data" / "snapshots"

    histogram_bin_width_mw: float = 500.0
    worst_hours_limit: int = 10
    coverage_levels_pct: list[int] = [50, 75, 80, 90, 95, 99]
    forecast_band_edges_mw: list[float] = [5000.0, 10000.0, 15000.0]

    # Local development only; every deployment is same-origin.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
