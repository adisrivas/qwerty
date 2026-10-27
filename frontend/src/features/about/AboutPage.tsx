import { useMeta } from '../../api/queries'
import { ErrorState, LoadingState } from '../../components/States'
import { fmtInt, ukDate, ukDateTime } from '../../lib/format'

export function AboutPage() {
  const meta = useMeta()
  if (meta.isPending) return <LoadingState label="Loading method and data" />
  if (meta.isError) return <ErrorState error={meta.error} />
  const m = meta.data

  return (
    <>
      <div className="page-head">
        <h1>Method and data</h1>
      </div>

      <section className="card prose">
        <h2>Method</h2>
        <ol>
          <li>
            For decision day D, select the latest WINDFOR issue published at or before the cutoff on
            D and use it for delivery day D+1. Issues published after the cutoff are never used.
          </li>
          <li>
            Average the two FUELHH half-hours into each forecast hour and compute error as forecast
            minus outturn. Positive error is under-delivery against forecast.
          </li>
          <li>
            Calibrate the uncertainty band for each decision day on the previous{' '}
            {m.calibration_lookback_days} completed delivery days only, and back-test it on the days
            that follow.
          </li>
        </ol>
      </section>

      <section className="card prose">
        <h2>Definitions</h2>
        <dl>
          <dt>Bias</dt>
          <dd>Mean error. Positive means the forecast runs high.</dd>
          <dt>MAE, RMSE</dt>
          <dd>Mean absolute error and root mean square error. RMSE weights large errors more.</dd>
          <dt>nMAE</dt>
          <dd>
            MAE as a percentage of mean outturn. MAPE is not used because it is unstable in calm
            hours.
          </dd>
          <dt>P10, P50, P90</dt>
          <dd>Percentiles of the signed error. P90 is the error exceeded in 10% of hours.</dd>
          <dt>Dependable wind</dt>
          <dd>Forecast minus the calibrated P90 error. The level reached in 90% of past hours.</dd>
          <dt>Skill score</dt>
          <dd>1 minus forecast MAE over persistence MAE. 0 equals persistence; 1 is perfect.</dd>
          <dt>Persistence</dt>
          <dd>Metered outturn at the same hour {m.persistence_lag_hours} hours earlier.</dd>
        </dl>
      </section>

      <section className="card prose">
        <h2>Assumptions</h2>
        <ul>
          {m.assumptions.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      </section>

      <section className="card prose">
        <h2>Data</h2>
        <dl>
          <dt>Decision days</dt>
          <dd>
            {ukDate(m.first_decision_date)} to {ukDate(m.last_decision_date)}. Default cutoff{' '}
            {m.default_cutoff_local} UK time.
          </dd>
          <dt>Source</dt>
          <dd>
            Elexon Insights, {m.snapshot?.source_base_url ?? 'not loaded'}. No API key required.
          </dd>
          {m.snapshot ? (
            <>
              <dt>Snapshot</dt>
              <dd>
                Taken {ukDateTime(m.snapshot.created_at)} UK time. Files are verified against their
                SHA-256 checksums at start-up.
              </dd>
              <dt>WINDFOR</dt>
              <dd>
                NESO wind generation forecast, hourly. {fmtInt(m.snapshot.windfor.row_count)} rows,{' '}
                {m.forecast_issue_count} issues, published{' '}
                {m.snapshot.windfor.params['publishDateTimeFrom']?.slice(0, 10)} to{' '}
                {m.snapshot.windfor.params['publishDateTimeTo']?.slice(0, 10)}.
              </dd>
              <dt>FUELHH</dt>
              <dd>
                Metered wind outturn, half-hourly average MW. {fmtInt(m.snapshot.fuelhh.row_count)}{' '}
                rows, settlement dates {m.snapshot.fuelhh.params['settlementDateFrom']} to{' '}
                {m.snapshot.fuelhh.params['settlementDateTo']}.
              </dd>
            </>
          ) : null}
        </dl>
      </section>
    </>
  )
}
