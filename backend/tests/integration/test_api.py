"""End-to-end tests of the HTTP API against the synthetic snapshot with known answers."""

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app
from tests.fixtures import synthetic

NORMAL_DAY = "2026-01-10"  # 09:30 issue on time -> bias 700
LATE_DAY = synthetic.LATE_DAY.isoformat()  # 09:30 late -> falls back to 07:30, bias 800
GAP_DAY = "2026-01-12"  # delivery 13 Jan has a missing half-hour -> 23 pairs


def test_health_and_meta(client: TestClient) -> None:
    health = client.get("/api/health").json()
    assert health == {"status": "ok", "forecast_issues": 64, "actual_points": 239}

    meta = client.get("/api/v1/meta").json()
    assert meta["first_decision_date"] == "2026-01-10"
    assert meta["last_decision_date"] == "2026-01-12"
    assert meta["default_cutoff_local"] == "09:50"
    assert meta["timezone"] == "Europe/London"
    assert meta["snapshot"]["windfor"]["row_count"] == 64 * 73
    assert meta["snapshot"]["notes"] == ["synthetic"]
    assert len(meta["assumptions"]) >= 5


def test_decision_days_index(client: TestClient) -> None:
    body = client.get("/api/v1/decision-days").json()
    assert body["cutoff_local"] == "09:50"
    days = body["days"]
    assert [d["decision_date"] for d in days] == ["2026-01-10", "2026-01-11", "2026-01-12"]
    assert days[0]["selected_issue_time"] == "2026-01-10T09:30:00Z"
    assert days[1]["selected_issue_time"] == "2026-01-11T07:30:00Z"  # late 09:30 skipped
    assert days[2]["hours_with_actuals"] == 23


def test_forecast_view_normal_day(client: TestClient) -> None:
    body = client.get(f"/api/v1/forecast?decision_date={NORMAL_DAY}").json()
    assert body["delivery_date"] == "2026-01-11"
    assert body["cutoff_utc"] == "2026-01-10T09:50:00Z"
    selected = body["selected_issue"]
    assert selected["issue_time"] == "2026-01-10T09:30:00Z"
    assert selected["slot_label"] == "09:30"
    assert selected["available_at_cutoff"] is True
    assert selected["minutes_before_cutoff"] == 20
    assert selected["coverage_hours"] == 24
    assert len(selected["points"]) == 24

    # Every issue that touches the delivery day is listed, flagged by availability.
    flags = {(i["issue_time"], i["available_at_cutoff"]) for i in body["issues"]}
    assert ("2026-01-10T11:30:00Z", False) in flags
    assert ("2026-01-09T22:30:00Z", True) in flags

    assert len(body["actuals_half_hourly"]) == 48
    assert len(body["actuals_hourly"]) == 24
    assert len(body["comparison"]) == 24
    assert all(p["error_mw"] == 700.0 for p in body["comparison"])
    assert body["summary"]["bias_mw"] == 700.0
    assert body["summary"]["mae_mw"] == 700.0
    assert body["summary"]["rmse_mw"] == pytest.approx(700.0)
    assert body["summary"]["buffer_p90_mw"] == 700.0
    assert body["energy"]["error_mwh"] == pytest.approx(700.0 * 24)
    # Persistence (actual two days earlier) is 20 MW low every hour; the synthetic forecast
    # is 700 MW high, so the skill score is strongly negative.
    assert body["baseline"]["name"] == "persistence_48h"
    assert body["baseline"]["hours"] == 24
    assert body["baseline"]["mae_mw"] == pytest.approx(20.0)
    assert body["baseline"]["bias_mw"] == pytest.approx(-20.0)
    assert body["baseline"]["skill_score"] == pytest.approx(1 - 700 / 20)
    # Too little history for a band: the API says so instead of fabricating one.
    assert body["calibration"] is None
    assert body["band"] == []
    assert body["dependable_energy_mwh"] is None
    assert any("No calibrated band" in note for note in body["notes"])


def test_forecast_view_falls_back_when_issue_is_late(client: TestClient) -> None:
    body = client.get(f"/api/v1/forecast?decision_date={LATE_DAY}").json()
    assert body["selected_issue"]["issue_time"] == "2026-01-11T07:30:00Z"
    assert body["summary"]["bias_mw"] == 800.0
    late = next(i for i in body["issues"] if i["issue_time"] == "2026-01-11T12:25:00Z")
    assert late["available_at_cutoff"] is False
    assert late["minutes_before_cutoff"] == -155


def test_forecast_view_respects_custom_cutoff(client: TestClient) -> None:
    body = client.get(f"/api/v1/forecast?decision_date={NORMAL_DAY}&cutoff=09:20").json()
    assert body["cutoff_local"] == "09:20"
    assert body["selected_issue"]["issue_time"] == "2026-01-10T07:30:00Z"
    assert body["summary"]["bias_mw"] == 800.0

    early = client.get(f"/api/v1/forecast?decision_date={NORMAL_DAY}&cutoff=02:00").json()
    # Before 02:30 on D, the latest issue is 22:30 on D-1 (slot bias 300).
    assert early["selected_issue"]["issue_time"] == "2026-01-09T22:30:00Z"
    assert early["summary"]["bias_mw"] == 300.0


def test_forecast_view_excludes_incomplete_hour_and_explains(client: TestClient) -> None:
    body = client.get(f"/api/v1/forecast?decision_date={GAP_DAY}").json()
    assert len(body["actuals_half_hourly"]) == 47
    assert len(body["actuals_hourly"]) == 24
    incomplete = [h for h in body["actuals_hourly"] if not h["is_complete"]]
    assert len(incomplete) == 1
    assert incomplete[0]["target_time"] == "2026-01-13T02:00:00Z"
    assert len(body["comparison"]) == 23
    assert any("excluded" in note for note in body["notes"])


def test_accuracy_report_over_all_days(client: TestClient) -> None:
    body = client.get("/api/v1/accuracy").json()
    assert body["from_decision_date"] == "2026-01-10"
    assert body["to_decision_date"] == "2026-01-12"
    assert body["days_requested"] == 3
    assert body["days_compared"] == 3
    assert body["days_without_forecast"] == []
    assert body["hours_compared"] == 24 + 24 + 23

    # 24 hours at 700, 24 at 800, 23 at 700
    expected_bias = (24 * 700 + 24 * 800 + 23 * 700) / 71
    assert body["overall"]["bias_mw"] == pytest.approx(expected_bias)
    assert body["overall"]["mae_mw"] == pytest.approx(expected_bias)
    assert body["overall"]["max_over_forecast_mw"] == 800.0
    assert body["overall"]["max_under_forecast_mw"] == 0.0
    assert body["guidance"]["buffer_p90_mw"] == 800.0
    assert "exceeded" in body["guidance"]["explanation"]
    options = {o["confidence_pct"]: o["buffer_mw"] for o in body["guidance"]["coverage_options"]}
    assert options[90] == pytest.approx(800.0)
    assert options[50] == pytest.approx(700.0)
    assert options[99] == pytest.approx(800.0)
    assert body["baseline"]["mae_mw"] == pytest.approx(20.0)
    assert body["baseline"]["hours"] == 71
    assert body["band_backtest"] is None  # no day has enough history
    bands = {b["label"]: b for b in body["by_forecast_band"]}
    assert sum(b["summary"]["count"] for b in bands.values()) == 71

    daily = {d["decision_date"]: d for d in body["daily"]}
    assert daily["2026-01-11"]["summary"]["bias_mw"] == 800.0
    assert daily["2026-01-12"]["hours_compared"] == 23

    hours = {h["hour"]: h["summary"]["count"] for h in body["by_hour_of_day"]}
    assert hours[2] == 2  # the gap hour is missing on one day
    assert hours[5] == 3

    slots = {s["slot_label"]: s for s in body["by_issue_slot"]}
    assert slots["09:30"]["days"] == 2  # late day published at 12:25 instead
    assert slots["12:25"]["days"] == 1
    assert slots["09:30"]["available_at_cutoff"] is True
    assert slots["11:30"]["available_at_cutoff"] is False
    assert slots["22:30"]["summary"]["bias_mw"] == 300.0

    assert body["histogram"]["bin_width_mw"] == 500.0
    assert sum(b["count"] for b in body["histogram"]["bins"]) == 71
    assert body["worst_over_forecast_hours"][0]["error_mw"] == 800.0
    assert body["worst_under_forecast_hours"] == []


def test_accuracy_report_subrange_and_validation(client: TestClient) -> None:
    body = client.get("/api/v1/accuracy?from=2026-01-11&to=2026-01-11").json()
    assert body["hours_compared"] == 24
    assert body["overall"]["bias_mw"] == 800.0

    reversed_range = client.get("/api/v1/accuracy?from=2026-01-12&to=2026-01-10")
    assert reversed_range.status_code == 400
    assert reversed_range.headers["content-type"].startswith("application/problem+json")
    assert "to_date" in reversed_range.json()["detail"]


def test_out_of_scope_and_malformed_requests_are_problem_details(client: TestClient) -> None:
    out = client.get("/api/v1/forecast?decision_date=2026-03-01")
    assert out.status_code == 400
    problem = out.json()
    assert problem["title"] == "Date out of supported scope"
    assert problem["supported_from"] == "2026-01-10"
    assert problem["instance"] == "/api/v1/forecast"

    bad = client.get("/api/v1/forecast?decision_date=not-a-date")
    assert bad.status_code == 422
    assert "decision_date" in bad.json()["errors"]

    missing = client.get("/api/v1/forecast")
    assert missing.status_code == 422

    bad_cutoff = client.get(f"/api/v1/forecast?decision_date={NORMAL_DAY}&cutoff=25:99")
    assert bad_cutoff.status_code == 422


def test_csv_export(client: TestClient) -> None:
    response = client.get("/api/v1/accuracy/export.csv?from=2026-01-10&to=2026-01-10")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    lines = response.text.strip().splitlines()
    assert lines[0] == (
        "decision_date,delivery_date,issue_time_utc,target_time_utc,forecast_mw,actual_mw,error_mw"
    )
    assert len(lines) == 25
    assert lines[1].startswith("2026-01-10,2026-01-11,2026-01-10T09:30:00+00:00,")
    assert lines[1].endswith(",700.0")


def test_api_reports_503_when_snapshot_is_missing(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        snapshot_dir=tmp_path,
        first_decision_date=date(2026, 1, 10),
        last_decision_date=date(2026, 1, 12),
        log_level="ERROR",
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        response = client.get("/api/v1/meta")
    assert response.status_code == 503
    assert response.json()["title"] == "Data unavailable"
