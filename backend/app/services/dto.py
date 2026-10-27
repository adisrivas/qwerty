"""Response shapes (data transfer objects) returned by the services and the API.

Field names carry their unit (``_mw``, ``_mwh``, ``_pct``, ``_minutes``) so a reader of the
JSON never has to guess. All timestamps are ISO-8601 in UTC.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.metrics import ErrorSummary


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True)


class PointDTO(_Base):
    """A timestamped MW value."""

    target_time: datetime
    generation_mw: float


class HourlyActualDTO(_Base):
    """Hourly-mean actual with completeness information."""

    target_time: datetime
    generation_mw: float
    periods_used: int
    is_complete: bool


class ErrorPairDTO(_Base):
    """Forecast vs actual for one hour. ``error_mw = forecast_mw - actual_mw``."""

    target_time: datetime
    forecast_mw: float
    actual_mw: float
    error_mw: float


class ErrorSummaryDTO(_Base):
    """Error statistics. Positive error means the forecast was higher than reality."""

    count: int
    mean_actual_mw: float
    mean_forecast_mw: float
    bias_mw: float
    mae_mw: float
    rmse_mw: float
    nmae_pct: float
    p10_mw: float
    p50_mw: float
    p90_mw: float
    max_over_forecast_mw: float
    max_under_forecast_mw: float
    buffer_p90_mw: float = Field(
        description="MW to add on top of the forecast to be covered in 90% of hours."
    )

    @classmethod
    def from_domain(cls, summary: ErrorSummary) -> ErrorSummaryDTO:
        """Copy a domain summary."""
        return cls(
            count=summary.count,
            mean_actual_mw=summary.mean_actual_mw,
            mean_forecast_mw=summary.mean_forecast_mw,
            bias_mw=summary.bias_mw,
            mae_mw=summary.mae_mw,
            rmse_mw=summary.rmse_mw,
            nmae_pct=summary.nmae_pct,
            p10_mw=summary.p10_mw,
            p50_mw=summary.p50_mw,
            p90_mw=summary.p90_mw,
            max_over_forecast_mw=summary.max_over_forecast_mw,
            max_under_forecast_mw=summary.max_under_forecast_mw,
            buffer_p90_mw=summary.buffer_p90_mw,
        )


class EnergyDTO(_Base):
    """Daily energy totals over the hours that could be compared."""

    hours: int
    forecast_mwh: float
    actual_mwh: float
    error_mwh: float


class WindowDTO(_Base):
    """A half-open UTC time window ``[start, end)``."""

    start: datetime
    end: datetime


class BaselineDTO(_Base):
    """A naive forecast to judge the real one against."""

    name: str = Field(
        description="e.g. 'persistence_48h': actual at the same hour two days earlier."
    )
    hours: int
    mae_mw: float
    bias_mw: float
    skill_score: float | None = Field(
        description="1 - MAE_forecast / MAE_baseline. 0 = no better than naive, 1 = perfect."
    )


class CalibrationDTO(_Base):
    """Error quantiles learned only from delivery days completed before the decision."""

    window_from_decision_date: date
    window_to_decision_date: date
    days_used: int
    hours_used: int
    bias_mw: float
    p10_mw: float
    p50_mw: float
    p90_mw: float


class BandPointDTO(_Base):
    """Forecast for one hour with its calibrated range (all MW, floored at zero)."""

    target_time: datetime
    forecast_mw: float
    dependable_mw: float = Field(
        description="forecast - P90(error): reached in 9 past hours in 10."
    )
    expected_mw: float = Field(description="forecast - P50(error): median-bias-corrected.")
    optimistic_mw: float = Field(description="forecast - P10(error): upper edge of the band.")


class IssueDTO(_Base):
    """One forecast publication restricted to the delivery day."""

    issue_time: datetime
    slot_label: str = Field(description="Local wall-clock publication time, e.g. '09:30'.")
    available_at_cutoff: bool
    minutes_before_cutoff: int = Field(
        description="Positive when published before the cutoff, negative when after."
    )
    coverage_hours: int = Field(description="Hours of the delivery day this issue covers.")
    points: list[PointDTO]


class DecisionViewDTO(_Base):
    """Everything the desk needs for one decision day (client question 1)."""

    decision_date: date
    delivery_date: date
    timezone: str
    cutoff_local: str
    cutoff_utc: datetime
    delivery_window: WindowDTO
    selected_issue: IssueDTO | None
    issues: list[IssueDTO]
    calibration: CalibrationDTO | None
    band: list[BandPointDTO]
    dependable_energy_mwh: float | None = Field(
        description="Sum of dependable_mw over the delivery day; None without calibration."
    )
    actuals_half_hourly: list[PointDTO]
    actuals_hourly: list[HourlyActualDTO]
    comparison: list[ErrorPairDTO]
    summary: ErrorSummaryDTO | None
    baseline: BaselineDTO | None
    energy: EnergyDTO | None
    notes: list[str]


class DailyAccuracyDTO(_Base):
    """Accuracy of the as-of forecast for one decision day."""

    decision_date: date
    delivery_date: date
    issue_time: datetime | None
    hours_compared: int
    summary: ErrorSummaryDTO | None
    energy: EnergyDTO | None


class HourOfDayDTO(_Base):
    """Accuracy for one local hour of the day across all compared days."""

    hour: int
    summary: ErrorSummaryDTO


class IssueSlotDTO(_Base):
    """Accuracy if the desk had used the issue published at this slot on the decision day."""

    slot_label: str
    available_at_cutoff: bool
    days: int
    summary: ErrorSummaryDTO


class ForecastBandDTO(_Base):
    """Accuracy for hours whose forecast fell in ``[lower_mw, upper_mw)``."""

    label: str
    lower_mw: float
    upper_mw: float | None = Field(description="None for the open-ended top band.")
    summary: ErrorSummaryDTO


class HistogramBinDTO(_Base):
    """Half-open bin ``[lower_mw, upper_mw)``."""

    lower_mw: float
    upper_mw: float
    count: int


class HistogramDTO(_Base):
    """Distribution of signed hourly errors."""

    bin_width_mw: float
    bins: list[HistogramBinDTO]


class WorstHourDTO(_Base):
    """An extreme hour, linked back to the decision day that produced it."""

    decision_date: date
    delivery_date: date
    target_time: datetime
    forecast_mw: float
    actual_mw: float
    error_mw: float


class CoverageOptionDTO(_Base):
    """Buffer needed to be covered in ``confidence_pct`` of hours."""

    confidence_pct: int
    buffer_mw: float
    pct_of_mean_actual: float


class ProcurementGuidanceDTO(_Base):
    """Plain-language translation of the statistics into a buying rule."""

    bias_mw: float
    buffer_p90_mw: float
    buffer_p90_pct_of_mean_actual: float
    coverage_options: list[CoverageOptionDTO]
    explanation: str


class BandBacktestDTO(_Base):
    """Did the out-of-sample 90% band actually cover 90% of hours?"""

    target_pct: int
    days_checked: int
    days_without_history: int
    hours_checked: int
    hours_covered: int
    coverage_pct: float


class AccuracyReportDTO(_Base):
    """Quantified forecast error over a range of decision days (client question 2)."""

    from_decision_date: date
    to_decision_date: date
    timezone: str
    cutoff_local: str
    days_requested: int
    days_compared: int
    days_without_forecast: list[date]
    hours_compared: int
    overall: ErrorSummaryDTO
    baseline: BaselineDTO | None
    guidance: ProcurementGuidanceDTO
    band_backtest: BandBacktestDTO | None
    daily: list[DailyAccuracyDTO]
    by_hour_of_day: list[HourOfDayDTO]
    by_issue_slot: list[IssueSlotDTO]
    by_forecast_band: list[ForecastBandDTO]
    histogram: HistogramDTO
    worst_over_forecast_hours: list[WorstHourDTO]
    worst_under_forecast_hours: list[WorstHourDTO]


class DecisionDayDTO(_Base):
    """One row of the decision-day index."""

    decision_date: date
    delivery_date: date
    selected_issue_time: datetime | None
    hours_with_actuals: int


class DecisionDaysDTO(_Base):
    """All decision days in scope."""

    cutoff_local: str
    days: list[DecisionDayDTO]


class SnapshotFileDTO(_Base):
    """Provenance of one snapshot file."""

    file: str
    row_count: int
    sha256: str
    endpoint: str
    params: dict[str, str]


class SnapshotDTO(_Base):
    """Provenance of the data the app is serving."""

    created_at: datetime
    source_base_url: str
    windfor: SnapshotFileDTO
    fuelhh: SnapshotFileDTO
    notes: list[str]


class MetaDTO(_Base):
    """Scope, defaults and provenance, shown in the app footer and About page."""

    app_name: str
    version: str
    environment: str
    timezone: str
    first_decision_date: date
    last_decision_date: date
    default_cutoff_local: str
    calibration_lookback_days: int
    calibration_min_days: int
    persistence_lag_hours: int
    forecast_issue_count: int
    actual_point_count: int
    snapshot: SnapshotDTO | None
    assumptions: list[str]
