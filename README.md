# Day-ahead Wind Forecast

A web application for a UK energy supplier's day-ahead power buying desk. It answers two
questions with Elexon's public data, for every purchase decision made in January 2026:

1. **Which national wind forecast could the desk act on when the auction closed?**
  For decision day D it selects the newest NESO wind forecast issue (Elexon `WINDFOR`) published
   at or before the gate-closure cutoff (default 09:50 UK time, the N2EX day-ahead auction), shows
   it for delivery day D+1, and shows how it sat against the day's eight publication slots.
2. **How wrong was that forecast, in numbers the desk can buy against?**
  It compares the forecast with metered wind outturn (Elexon `FUELHH`, fuel type `WIND`),
   reports bias, MAE, RMSE, percentiles, error by hour of day, by forecast level and by
   publication slot, and turns the distribution into a procurement buffer at a chosen coverage
   level. A calibrated uncertainty band for each decision day is learned only from days that
   had already completed, and is back-tested.


|                         |                                                                                              |
| ----------------------- | -------------------------------------------------------------------------------------------- |
| **Live application**    | [https://windforecast-ten.vercel.app](https://windforecast-ten.vercel.app)                   |
| **API documentation**   | [https://windforecast-ten.vercel.app/api/docs](https://windforecast-ten.vercel.app/api/docs) |
| **Start locally**       | `make setup && make run`, or `docker compose up --build` (details below)                     |
| **Repository contents** | listed [below](#repository-contents)                                                         |


---



## Headline findings for January 2026 (09:50 cutoff, 744 hours)


| Measure                                        | Value                                      |
| ---------------------------------------------- | ------------------------------------------ |
| Mean error (forecast minus actual)             | +1,730 MW (forecast runs high)             |
| Mean absolute error                            | 2,013 MW (17.8 % of mean actual)           |
| RMSE                                           | 2,506 MW                                   |
| P90 of error (buffer for 90 % cover)           | +4,144 MW                                  |
| Skill vs 48-hour persistence                   | 0.54 (the forecast halves the naive error) |
| Out-of-sample 90 % band coverage               | 87.1 % of hours (target 90 %)              |
| Bias when forecast at or above 15 GW vs 0-5 GW | +2,753 MW vs +136 MW                       |


The last row is the important one for the client: the over-forecast is concentrated in
high-wind hours, which is the signature of curtailment (wind turned down by the system operator
for network constraints) rather than of a poor weather forecast. The app says so in its
assumptions rather than presenting the gap as pure forecast error.

## How to start the application

Prerequisites: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22, and Docker if you
want the container route. No API keys or environment variables are required; the January 2026
data is committed to the repository.

**Option A: Docker (one command)**

```bash
docker compose up --build
# application: http://localhost:8080   API: http://localhost:8000/api/docs
```

**Option B: local development servers**

```bash
make setup      # backend: uv sync   frontend: npm ci
make run        # backend on http://localhost:8000, frontend on http://localhost:5173
```

Without make:

```bash
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm ci && npm run dev        # proxies /api to :8000
```

**Tests and checks**

```bash
make test       # pytest (backend) and vitest (frontend)
make lint       # ruff, mypy, import-linter, oxlint, tsc, prettier
```

Other targets: `make refresh-data` (re-download from Elexon), `make openapi` (regenerate the
frontend's TypeScript API types), `make help`.

## How it works in one diagram

```
Elexon Insights API ──(scripts/refresh_snapshot.py, once)──► backend/data/snapshots/*.json + manifest (SHA-256)
                                                                       │
                                               FastAPI loads & verifies at start-up
                                                                       │
   React SPA ── /api/v1/forecast?decision_date&cutoff ──► services.decision ──► domain.selection / alignment / calibration
             ── /api/v1/accuracy?from&to&cutoff ────────► services.accuracy ──► domain.metrics
```

- The committed snapshot covers 14 Dec 2025 to 2 Feb 2026 (408 forecast issues, 2,304 half-hour
actuals). December is history for calibration and the persistence baseline; decision days are
1-31 January 2026 only.
- The domain layer is pure Python with no I/O; layering is enforced by import-linter.
- The frontend's API types are generated from the backend's OpenAPI document.

## Assumptions (also shown in the app under Method & data)

- Decision day D is the day the desk bids; delivery day is D+1 (UK calendar day).
- The forecast used is the newest `WINDFOR` issue with `publishTime` at or before the cutoff on D. Nothing
published later is ever used. The cutoff is a parameter (presets 09:50 N2EX and 09:20 EPEX).
- `WINDFOR` is hourly and `FUELHH` is half-hourly average MW; the two half-hours are averaged to
the hour starting at the forecast timestamp. Hours with a missing half-hour are shown but
excluded from statistics.
- Error is forecast minus actual. Positive means less wind arrived than planned, which is the
costly direction for a buyer.
- The uncertainty band for decision day D uses errors from delivery days that completed before D
(14-day window, minimum 5 days). The persistence baseline is the actual at the same hour 48
hours earlier.
- Both datasets cover transmission-connected wind in Great Britain only. Actuals include
curtailment.



## Repository contents



### Top level


| Path                         | Purpose                                                                                            |
| ---------------------------- | -------------------------------------------------------------------------------------------------- |
| `README.md`                  | This file.                                                                                         |
| `docs/design.md`             | Software design for technical review: layers, algorithms, tests, trade-offs rejected, limitations. |
| `docs/pitch.md`              | Client presentation script.                                                                        |
| `backend/`                   | Python 3.12 FastAPI service (see below).                                                           |
| `frontend/`                  | Vite + React 19 + TypeScript client (see below).                                                   |
| `api/index.py`               | Vercel entry point; imports the FastAPI app so it runs as a Python serverless function.            |
| `requirements.txt`           | Runtime dependencies for the Vercel function (mirrors `backend/pyproject.toml`).                   |
| `vercel.json`                | Vercel build command, output directory, function settings and rewrites.                            |
| `.vercelignore`              | Files excluded from the Vercel upload.                                                             |
| `docker/backend.Dockerfile`  | Multi-stage backend image (uv, non-root user, health check).                                       |
| `docker/frontend.Dockerfile` | Frontend build served by nginx.                                                                    |
| `docker/nginx.conf`          | nginx config: static files plus `/api` proxy to the backend.                                       |
| `docker-compose.yml`         | Two-service stack: backend on 8000, frontend on 8080.                                              |
| `Makefile`                   | Developer entry points (`make help`).                                                              |
| `.github/workflows/ci.yml`   | CI: lint, type checks, layering, tests, both Docker builds, container smoke test.                  |
| `.pre-commit-config.yaml`    | Pre-commit hooks mirroring CI.                                                                     |
| `.env.example`               | Every `WINDFORECAST_*` setting with its default.                                                   |




### `backend/`


| Path                                           | Purpose                                                                                      |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `app/main.py`                                  | Application factory, start-up snapshot load, static file mount for single-container deploys. |
| `app/core/config.py`                           | Settings (scope dates, cutoff, calibration window, Elexon URL, presentation defaults).       |
| `app/core/errors.py`                           | Problem-details error responses.                                                             |
| `app/core/logging.py`                          | JSON logging.                                                                                |
| `app/domain/models.py`                         | Forecast issue, forecast point, actual, hourly actual, error pair.                           |
| `app/domain/selection.py`                      | Delivery window, cutoff instant, as-of issue selection.                                      |
| `app/domain/alignment.py`                      | Half-hourly to hourly averaging and forecast/actual pairing.                                 |
| `app/domain/calibration.py`                    | Error quantiles from past days, uncertainty band, coverage check.                            |
| `app/domain/metrics.py`                        | Bias, MAE, RMSE, nMAE, percentiles, skill score, histogram, grouping.                        |
| `app/data/elexon_client.py`                    | Chunked, retrying HTTP client for the two Elexon stream endpoints.                           |
| `app/data/parsers.py`                          | Raw rows to domain objects, strict validation, deduplication.                                |
| `app/data/snapshot.py`                         | Write and verify the committed snapshot and its manifest.                                    |
| `app/data/repository.py`                       | In-memory, time-indexed access to issues and actuals.                                        |
| `app/services/decision.py`                     | Builds the decision view (client question 1).                                                |
| `app/services/accuracy.py`                     | Builds the accuracy report and CSV export (client question 2).                               |
| `app/services/catalog.py`                      | Decision-day index and `/meta`.                                                              |
| `app/services/common.py`                       | Shared steps: compare a day, admissible history, persistence baseline.                       |
| `app/services/dto.py`                          | Response models with units in field names.                                                   |
| `app/api/routes.py`, `app/api/deps.py`         | HTTP routes and dependencies.                                                                |
| `data/snapshots/`                              | `windfor.json`, `fuelhh_wind.json`, `manifest.json` (14 Dec 2025 to 2 Feb 2026).             |
| `scripts/refresh_snapshot.py`                  | Re-download the data and rewrite the snapshot.                                               |
| `tests/unit/`                                  | Domain, parser, client, snapshot and repository tests.                                       |
| `tests/integration/test_api.py`                | Every route against a synthetic dataset with known answers.                                  |
| `tests/integration/test_committed_snapshot.py` | Regression tests pinning the January headline numbers.                                       |
| `tests/fixtures/synthetic.py`                  | The synthetic dataset generator.                                                             |
| `pyproject.toml`, `uv.lock`                    | Dependencies and tool configuration (ruff, mypy, pytest, import-linter).                     |




### `frontend/`


| Path                                                             | Purpose                                                                           |
| ---------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `src/main.tsx`, `src/App.tsx`                                    | Entry point, router, query client.                                                |
| `src/api/client.ts`                                              | Typed fetch wrapper and problem-details handling.                                 |
| `src/api/queries.ts`                                             | TanStack Query hooks.                                                             |
| `src/api/schema.d.ts`                                            | TypeScript types generated from the backend OpenAPI document.                     |
| `src/features/decision/DecisionPage.tsx`                         | Decision view: controls, decision basis, tiles, chart, planner, hourly table.     |
| `src/features/accuracy/AccuracyPage.tsx`                         | Accuracy view: buffer, tiles, charts, worst hours, day table.                     |
| `src/features/about/AboutPage.tsx`                               | Method, definitions, assumptions, data provenance.                                |
| `src/components/`                                                | Layout, StatTile, Callout, AsOfPanel, IssueTimeline, CutoffField, Legend, States. |
| `src/components/charts/`                                         | Recharts components for each chart plus shared tooltip and axis settings.         |
| `src/lib/format.ts`                                              | Number, date and time formatting (UK local time).                                 |
| `src/lib/cutoffs.ts`, `src/lib/useChartTheme.ts`                 | Cutoff presets and chart colours.                                                 |
| `src/index.css`                                                  | Design tokens and all styles.                                                     |
| `src/test/`                                                      | Vitest setup, fixtures and page tests.                                            |
| `openapi.json`                                                   | OpenAPI document exported from the backend; source for `schema.d.ts`.             |
| `index.html`, `vite.config.ts`, `tsconfig*.json`, `package.json` | Build configuration.                                                              |




## Quality gates

Backend: ruff (format + lint), mypy `--strict`, import-linter, pytest (76 tests, 97 % coverage,
including a regression suite that pins the headline numbers above). Frontend: TypeScript strict,
oxlint, Prettier, Vitest (14 tests). CI runs all of it plus both Docker builds and a container
smoke test on every push.

## Deployment

- **Vercel** (as deployed): one project at the repository root. `vercel.json` builds the frontend
to static files and runs `api/index.py` as a Python 3.12 serverless function with the backend
package and snapshot included. `/api/*` is rewritten to the function, everything else to
`index.html`. Deploy with `vercel deploy --prod`.
- **Docker**: `docker compose up --build`, or run the backend image alone with
`WINDFORECAST_STATIC_DIR` pointing at a frontend build to serve both from one container (Heroku
container stack works this way).

Configuration is via `WINDFORECAST_*` environment variables; see `.env.example`.

## Data notes

- Endpoints: `GET /datasets/WINDFOR/stream` (publish-time filters only) and
`GET /datasets/FUELHH/stream?fuelType=WIND` (settlement-date filters) on
`https://data.elexon.co.uk/bmrs/api/v1`. No API key.
- `WINDFOR` issues cover 73 hours (21:00 D-1 to 21:00 D+2) and are published about eight times a
day; the Elexon glossary's "four per day" is out of date. One January issue arrived 55 minutes
late, which is why selection is by publish time rather than by slot.
- Refreshing the snapshot (`make refresh-data`) rewrites the files and manifest; the regression
test will flag any change in the headline numbers so it is reviewed deliberately.



## Use of AI tools

AI coding assistant Claude Code were used during development for parts of the implementation, tests and  
documentation. All design decisions, data verification against the live Elexon API and review of  
the results were carried out manually.