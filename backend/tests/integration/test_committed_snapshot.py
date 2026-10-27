"""Regression tests against the committed snapshot (16 Dec 2025 to 1 Feb 2026).

These pin the headline numbers the product shows the client. If the snapshot is refreshed
and Elexon has revised data, the expected values here must be reviewed deliberately.
"""

from datetime import UTC, date, datetime, time

import pytest

from app.core.config import Settings
from app.data.repository import WindDataRepository
from app.services.accuracy import build_accuracy_report
from app.services.catalog import build_decision_days
from app.services.decision import build_decision_view

pytestmark = pytest.mark.snapshot

SETTINGS = Settings(environment="test", log_level="ERROR")


def test_snapshot_extent(committed_repo: WindDataRepository) -> None:
    extent = committed_repo.extent()
    assert extent.issue_count == 408  # 51 days x 8 issues
    assert extent.actual_count == 2304  # 48 delivery days x 48 half-hours
    assert extent.first_issue_time == datetime(2025, 12, 14, 2, 30, tzinfo=UTC)
    assert extent.first_actual_time == datetime(2025, 12, 16, 0, 0, tzinfo=UTC)
    assert extent.last_actual_time == datetime(2026, 2, 1, 23, 30, tzinfo=UTC)


def test_every_decision_day_selects_the_0930_issue(committed_repo: WindDataRepository) -> None:
    index = build_decision_days(committed_repo, time(9, 50), SETTINGS)
    assert len(index.days) == 31
    for day in index.days:
        assert day.selected_issue_time is not None
        assert day.selected_issue_time.time() == time(9, 30)
        assert day.selected_issue_time.date() == day.decision_date
        assert day.hours_with_actuals == 24


def test_headline_numbers_for_january_2026(committed_repo: WindDataRepository) -> None:
    report = build_accuracy_report(
        committed_repo, date(2026, 1, 1), date(2026, 1, 31), time(9, 50), SETTINGS
    )
    assert report.hours_compared == 744
    assert report.days_compared == 31
    assert report.days_without_forecast == []
    assert report.overall.bias_mw == pytest.approx(1730, abs=1)
    assert report.overall.mae_mw == pytest.approx(2013, abs=1)
    assert report.overall.rmse_mw == pytest.approx(2506, abs=1)
    assert report.overall.p90_mw == pytest.approx(4144, abs=1)
    assert report.overall.bias_mw > 0  # the forecast over-predicts in January 2026

    slots = {s.slot_label: s for s in report.by_issue_slot}
    assert slots["09:30"].available_at_cutoff
    assert not slots["11:30"].available_at_cutoff
    # Later issues are more accurate on average, which is why the cutoff matters.
    assert (
        slots["22:30"].summary.mae_mw
        < slots["09:30"].summary.mae_mw
        < slots["02:30"].summary.mae_mw
    )


def test_baseline_band_and_regime_findings(committed_repo: WindDataRepository) -> None:
    report = build_accuracy_report(
        committed_repo, date(2026, 1, 1), date(2026, 1, 31), time(9, 50), SETTINGS
    )
    # The forecast roughly halves the error of "same hour two days ago".
    assert report.baseline is not None
    assert report.baseline.hours == 744
    assert report.baseline.mae_mw == pytest.approx(4340, abs=1)
    assert report.baseline.skill_score == pytest.approx(0.536, abs=0.005)

    # Coverage options are monotonic and the 90% option equals the P90 buffer.
    buffers = [o.buffer_mw for o in report.guidance.coverage_options]
    assert buffers == sorted(buffers)
    by_level = {o.confidence_pct: o.buffer_mw for o in report.guidance.coverage_options}
    assert by_level[90] == pytest.approx(report.overall.buffer_p90_mw)

    # Out-of-sample: every January day had 14 days of prior history; the 90% band held
    # in about 87% of hours, slightly under target because bias grew through the month.
    assert report.band_backtest is not None
    assert report.band_backtest.days_without_history == 0
    assert report.band_backtest.hours_checked == 744
    assert report.band_backtest.coverage_pct == pytest.approx(87.1, abs=0.2)

    # The over-forecast is concentrated in high-wind hours (curtailment signature).
    bands = {b.label: b.summary for b in report.by_forecast_band}
    assert bands["0-5 GW"].bias_mw < 300
    assert bands["≥ 15 GW"].bias_mw > 2500
    assert sum(b.count for b in bands.values()) == 744


def test_decision_view_band_is_out_of_sample(committed_repo: WindDataRepository) -> None:
    view = build_decision_view(committed_repo, date(2026, 1, 15), time(9, 50), SETTINGS)
    assert view.calibration is not None
    assert view.calibration.window_to_decision_date == date(2026, 1, 13)
    assert view.calibration.window_from_decision_date == date(2025, 12, 31)
    assert view.calibration.days_used == 14
    assert len(view.band) == 24
    for point in view.band:
        assert 0 <= point.dependable_mw <= point.expected_mw <= point.optimistic_mw
    assert view.dependable_energy_mwh is not None
    assert view.baseline is not None
    assert view.baseline.name == "persistence_48h"
