"""API routes. Each handler validates input, calls one service, returns its DTO."""

from __future__ import annotations

import csv
import io
from datetime import date, time
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import Config, Repo
from app.services.accuracy import build_accuracy_report, export_rows
from app.services.catalog import build_decision_days, build_meta
from app.services.decision import build_decision_view
from app.services.dto import AccuracyReportDTO, DecisionDaysDTO, DecisionViewDTO, MetaDTO

router = APIRouter(prefix="/api")
v1 = APIRouter(prefix="/v1", tags=["v1"])

CutoffParam = Annotated[
    time | None,
    Query(
        description="Local UK gate-closure time, HH:MM. Defaults to the configured cutoff "
        "(09:50, the N2EX GB day-ahead auction).",
        examples=["09:50", "09:20"],
    ),
]


class HealthDTO(BaseModel):
    """Liveness response."""

    status: str
    forecast_issues: int
    actual_points: int


@router.get("/health", response_model=HealthDTO, tags=["ops"])
def health(repo: Repo) -> HealthDTO:
    """Liveness and a quick sanity count of loaded data."""
    extent = repo.extent()
    return HealthDTO(
        status="ok", forecast_issues=extent.issue_count, actual_points=extent.actual_count
    )


@v1.get("/meta", response_model=MetaDTO)
def meta(repo: Repo, settings: Config) -> MetaDTO:
    """Scope, defaults, assumptions and data provenance."""
    return build_meta(repo, settings)


@v1.get("/decision-days", response_model=DecisionDaysDTO)
def decision_days(repo: Repo, settings: Config, cutoff: CutoffParam = None) -> DecisionDaysDTO:
    """Every supported decision day and the forecast issue that would be selected."""
    return build_decision_days(repo, cutoff or settings.default_cutoff, settings)


@v1.get("/forecast", response_model=DecisionViewDTO)
def forecast(
    repo: Repo,
    settings: Config,
    decision_date: Annotated[date, Query(description="Day the desk bids (YYYY-MM-DD).")],
    cutoff: CutoffParam = None,
) -> DecisionViewDTO:
    """Client question 1: the latest forecast available at the cutoff, plus context."""
    return build_decision_view(repo, decision_date, cutoff or settings.default_cutoff, settings)


@v1.get("/accuracy", response_model=AccuracyReportDTO)
def accuracy(
    repo: Repo,
    settings: Config,
    from_date: Annotated[
        date | None, Query(alias="from", description="First decision day, inclusive.")
    ] = None,
    to_date: Annotated[
        date | None, Query(alias="to", description="Last decision day, inclusive.")
    ] = None,
    cutoff: CutoffParam = None,
) -> AccuracyReportDTO:
    """Client question 2: quantified error of the as-of forecasts over a date range."""
    return build_accuracy_report(
        repo,
        from_date or settings.first_decision_date,
        to_date or settings.last_decision_date,
        cutoff or settings.default_cutoff,
        settings,
    )


@v1.get("/accuracy/export.csv", response_class=StreamingResponse)
def accuracy_export(
    repo: Repo,
    settings: Config,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    cutoff: CutoffParam = None,
) -> StreamingResponse:
    """Every compared hour as CSV, for the desk's own analysis."""
    rows = export_rows(
        repo,
        from_date or settings.first_decision_date,
        to_date or settings.last_decision_date,
        cutoff or settings.default_cutoff,
        settings,
    )

    def generate() -> io.StringIO:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerows(rows)
        buffer.seek(0)
        return buffer

    filename = "wind-forecast-accuracy.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


router.include_router(v1)
