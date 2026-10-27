import { useCallback, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, type AccuracyReport, type Meta, type WorstHour } from '../../api/client'
import { useAccuracy, useMeta } from '../../api/queries'
import { Callout } from '../../components/Callout'
import { CutoffField } from '../../components/CutoffField'
import { ErrorState, LoadingState } from '../../components/States'
import { StatTile } from '../../components/StatTile'
import { DailyBiasChart } from '../../components/charts/DailyBiasChart'
import { ErrorHistogramChart } from '../../components/charts/ErrorHistogramChart'
import { ForecastBandChart } from '../../components/charts/ForecastBandChart'
import { HourOfDayChart } from '../../components/charts/HourOfDayChart'
import { IssueSlotChart } from '../../components/charts/IssueSlotChart'
import {
  DATE_RE,
  TIME_RE,
  clampDate,
  fmtInt,
  fmtMW,
  fmtPct,
  fmtSignedMW,
  fmtSignedMWh,
  ukDateTime,
  ukShortDate,
  ukTime,
} from '../../lib/format'

function useAccuracyParams(meta: Meta | undefined) {
  const [params, setParams] = useSearchParams()
  const first = meta?.first_decision_date
  const last = meta?.last_decision_date
  const rawFrom = params.get('from') ?? ''
  const rawTo = params.get('to') ?? ''
  let from =
    first && last ? clampDate(DATE_RE.test(rawFrom) ? rawFrom : first, first, last) : undefined
  let to = first && last ? clampDate(DATE_RE.test(rawTo) ? rawTo : last, first, last) : undefined
  if (from && to && from > to) [from, to] = [to, from]
  const rawCutoff = params.get('cutoff') ?? ''
  const cutoff = TIME_RE.test(rawCutoff) ? rawCutoff : (meta?.default_cutoff_local ?? '09:50')

  const update = useCallback(
    (next: { from?: string; to?: string; cutoff?: string }) => {
      setParams(
        (prev) => {
          const p = new URLSearchParams(prev)
          for (const [k, v] of Object.entries(next)) if (v) p.set(k, v)
          return p
        },
        { replace: true },
      )
    },
    [setParams],
  )
  return { from, to, cutoff, first, last, update }
}

export function AccuracyPage() {
  const meta = useMeta()
  const { from, to, cutoff, first, last, update } = useAccuracyParams(meta.data)
  const report = useAccuracy(from, to, cutoff)
  const navigate = useNavigate()
  const openDay = useCallback(
    (decisionDate: string) => navigate(`/decision?date=${decisionDate}&cutoff=${cutoff}`),
    [navigate, cutoff],
  )

  return (
    <>
      <div className="page-head">
        <h1>Forecast accuracy</h1>
        <p>Forecast error against metered outturn and the resulting procurement buffer.</p>
      </div>

      <div className="controls">
        <label className="field" htmlFor="from-date">
          From decision day
          <input
            id="from-date"
            type="date"
            value={from ?? ''}
            min={first}
            max={to}
            disabled={!from}
            onChange={(e) => DATE_RE.test(e.target.value) && update({ from: e.target.value })}
          />
        </label>
        <label className="field" htmlFor="to-date">
          To decision day
          <input
            id="to-date"
            type="date"
            value={to ?? ''}
            min={from}
            max={last}
            disabled={!to}
            onChange={(e) => DATE_RE.test(e.target.value) && update({ to: e.target.value })}
          />
        </label>
        {first && last ? (
          <button className="btn" type="button" onClick={() => update({ from: first, to: last })}>
            Whole month
          </button>
        ) : null}
        <CutoffField value={cutoff} onChange={(c) => update({ cutoff: c })} />
        <a className="btn" href={api.accuracyCsvUrl({ from, to, cutoff })} download>
          Download CSV
        </a>
      </div>

      {meta.isError ? <ErrorState error={meta.error} /> : null}
      {report.isPending && !meta.isError ? <LoadingState label="Loading accuracy report" /> : null}
      {report.isError ? <ErrorState error={report.error} /> : null}
      {report.data ? <AccuracyContent report={report.data} onOpenDay={openDay} /> : null}
    </>
  )
}

function AccuracyContent({
  report,
  onOpenDay,
}: {
  report: AccuracyReport
  onOpenDay: (decisionDate: string) => void
}) {
  const o = report.overall
  const [level, setLevel] = useState(90)
  if (report.hours_compared === 0) {
    return (
      <Callout kind="warn" title="No comparable hours">
        No hours in this range have both a forecast at the cutoff and metered outturn.
      </Callout>
    )
  }
  const option =
    report.guidance.coverage_options.find((c) => c.confidence_pct === level) ??
    report.guidance.coverage_options[0]
  const backtest = report.band_backtest
  const skill = report.baseline?.skill_score

  return (
    <>
      <section className="card" aria-labelledby="guidance-title">
        <div className="card-head">
          <div>
            <h2 id="guidance-title">Procurement buffer</h2>
            <p>Volume to procure above the forecast at the selected confidence level.</p>
          </div>
          <div className="segmented" role="group" aria-label="Confidence level">
            {report.guidance.coverage_options.map((c) => (
              <button
                key={c.confidence_pct}
                type="button"
                aria-pressed={c.confidence_pct === level}
                onClick={() => setLevel(c.confidence_pct)}
              >
                {c.confidence_pct}%
              </button>
            ))}
          </div>
        </div>
        <div className="hero">
          <span className="hero-figure">
            {option ? fmtInt(option.buffer_mw) : '—'}
            <small>MW, covered in {level}% of hours</small>
          </span>
          <span className="secondary">
            {option ? fmtPct(option.pct_of_mean_actual) : '—'} of mean outturn,{' '}
            {report.hours_compared} hours, {report.days_compared} days, cutoff {report.cutoff_local}
          </span>
        </div>
        <p className="secondary">{report.guidance.explanation}</p>
        {backtest ? (
          <p className="secondary">
            Back-test: each day's {backtest.target_pct}% buffer, calibrated on prior days only,
            covered {backtest.hours_covered} of {backtest.hours_checked} hours (
            {fmtPct(backtest.coverage_pct)}, target {backtest.target_pct}%).
          </p>
        ) : null}
      </section>

      <div className="kpi-row">
        <StatTile
          label="Bias"
          value={fmtSignedMW(o.bias_mw).replace(' MW', '')}
          unit="MW"
          tone={o.bias_mw >= 0 ? 'over' : 'under'}
          hint={o.bias_mw >= 0 ? 'Forecast above outturn' : 'Forecast below outturn'}
        />
        <StatTile
          label="MAE"
          value={fmtInt(o.mae_mw)}
          unit="MW"
          hint={`${fmtPct(o.nmae_pct)} of mean outturn`}
        />
        <StatTile label="RMSE" value={fmtInt(o.rmse_mw)} unit="MW" />
        <StatTile label="Median error" value={fmtSignedMW(o.p50_mw).replace(' MW', '')} unit="MW" />
        <StatTile
          label="P90 error"
          value={fmtSignedMW(o.p90_mw).replace(' MW', '')}
          unit="MW"
          tone="over"
          hint="Exceeded in 10% of hours"
        />
        {skill !== null && skill !== undefined && report.baseline ? (
          <StatTile
            label="Skill vs persistence"
            value={fmtPct(skill * 100)}
            hint={`persistence MAE ${fmtMW(report.baseline.mae_mw)}`}
          />
        ) : null}
        <StatTile
          label="Largest error"
          value={fmtSignedMW(o.max_over_forecast_mw).replace(' MW', '')}
          unit="MW"
          tone="over"
          hint={`largest surplus ${fmtSignedMW(o.max_under_forecast_mw)}`}
        />
      </div>

      {report.days_without_forecast.length > 0 ? (
        <Callout kind="warn" title="Days without a forecast at cutoff">
          {report.days_without_forecast.map(ukShortDate).join(', ')} are excluded.
        </Callout>
      ) : null}

      <section className="card" aria-labelledby="daily-title">
        <div className="card-head">
          <div>
            <h2 id="daily-title">Daily mean error</h2>
            <p>Select a bar to open that day.</p>
          </div>
        </div>
        <DailyBiasChart daily={report.daily} onSelectDay={onOpenDay} />
      </section>

      <div className="grid-2">
        <section className="card" aria-labelledby="band-title">
          <div className="card-head">
            <h2 id="band-title">Error by forecast level</h2>
          </div>
          <ForecastBandChart bands={report.by_forecast_band} />
        </section>
        <section className="card" aria-labelledby="hist-title">
          <div className="card-head">
            <div>
              <h2 id="hist-title">Distribution of hourly errors</h2>
              <p>{report.histogram.bin_width_mw} MW bins</p>
            </div>
          </div>
          <ErrorHistogramChart report={report} />
        </section>
      </div>

      <div className="grid-2">
        <section className="card" aria-labelledby="hod-title">
          <div className="card-head">
            <h2 id="hod-title">Mean error by hour of day</h2>
          </div>
          <HourOfDayChart hours={report.by_hour_of_day} />
        </section>
        <section className="card" aria-labelledby="slot-title">
          <div className="card-head">
            <div>
              <h2 id="slot-title">Error by publication time</h2>
              <p>Grey bars were published after the cutoff.</p>
            </div>
          </div>
          <IssueSlotChart slots={report.by_issue_slot} cutoff={report.cutoff_local} />
        </section>
      </div>

      <div className="grid-2">
        <WorstTable
          title="Largest under-delivery"
          hours={report.worst_over_forecast_hours}
          onOpenDay={onOpenDay}
        />
        <WorstTable
          title="Largest over-delivery"
          hours={report.worst_under_forecast_hours}
          onOpenDay={onOpenDay}
        />
      </div>

      <section className="card" aria-labelledby="days-title">
        <div className="card-head">
          <h2 id="days-title">Day by day</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Delivery day</th>
                <th scope="col">Issue used</th>
                <th scope="col">Bias MW</th>
                <th scope="col">MAE MW</th>
                <th scope="col">P90 MW</th>
                <th scope="col">Energy error MWh</th>
              </tr>
            </thead>
            <tbody>
              {report.daily.map((d) => (
                <tr key={d.decision_date}>
                  <td>
                    <a
                      href={`/decision?date=${d.decision_date}&cutoff=${report.cutoff_local}`}
                      onClick={(e) => {
                        e.preventDefault()
                        onOpenDay(d.decision_date)
                      }}
                    >
                      {ukShortDate(d.delivery_date)}
                    </a>
                  </td>
                  <td className="mono">
                    {d.issue_time ? ukDateTime(d.issue_time) : 'none at cutoff'}
                  </td>
                  <td
                    className={`num ${d.summary ? (d.summary.bias_mw >= 0 ? 'pos' : 'neg') : ''}`}
                  >
                    {d.summary ? fmtSignedMW(d.summary.bias_mw).replace(' MW', '') : '—'}
                  </td>
                  <td className="num">{d.summary ? fmtInt(d.summary.mae_mw) : '—'}</td>
                  <td className="num">
                    {d.summary ? fmtSignedMW(d.summary.p90_mw).replace(' MW', '') : '—'}
                  </td>
                  <td className="num">
                    {d.energy ? fmtSignedMWh(d.energy.error_mwh).replace(' MWh', '') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}

function WorstTable({
  title,
  hours,
  onOpenDay,
}: {
  title: string
  hours: WorstHour[]
  onOpenDay: (decisionDate: string) => void
}) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>{title}</h2>
      </div>
      {hours.length === 0 ? (
        <p className="muted">None in this range.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Hour (UK)</th>
                <th scope="col">Forecast MW</th>
                <th scope="col">Outturn MW</th>
                <th scope="col">Error MW</th>
              </tr>
            </thead>
            <tbody>
              {hours.map((h) => (
                <tr key={h.target_time}>
                  <td>
                    <a
                      href={`/decision?date=${h.decision_date}`}
                      onClick={(e) => {
                        e.preventDefault()
                        onOpenDay(h.decision_date)
                      }}
                    >
                      {ukShortDate(h.delivery_date)} {ukTime(h.target_time)}
                    </a>
                  </td>
                  <td className="num">{fmtInt(h.forecast_mw)}</td>
                  <td className="num">{fmtInt(h.actual_mw)}</td>
                  <td className={`num ${h.error_mw >= 0 ? 'pos' : 'neg'}`}>
                    {fmtSignedMW(h.error_mw).replace(' MW', '')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
