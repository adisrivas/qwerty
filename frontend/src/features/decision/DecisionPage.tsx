import { useCallback, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { DecisionView, Meta } from '../../api/client'
import { useForecast, useMeta } from '../../api/queries'
import { AsOfPanel } from '../../components/AsOfPanel'
import { Callout } from '../../components/Callout'
import { CutoffField } from '../../components/CutoffField'
import { IssueTimeline } from '../../components/IssueTimeline'
import { ErrorState, LoadingState } from '../../components/States'
import { StatTile } from '../../components/StatTile'
import { ForecastVsActualChart } from '../../components/charts/ForecastVsActualChart'
import {
  DATE_RE,
  TIME_RE,
  addDays,
  clampDate,
  fmtInt,
  fmtMW,
  fmtPct,
  fmtSignedMW,
  fmtSignedMWh,
  ukDate,
  ukTime,
} from '../../lib/format'

function useDecisionParams(meta: Meta | undefined) {
  const [params, setParams] = useSearchParams()
  const first = meta?.first_decision_date
  const last = meta?.last_decision_date
  const rawDate = params.get('date') ?? ''
  const date =
    first && last ? clampDate(DATE_RE.test(rawDate) ? rawDate : last, first, last) : undefined
  const rawCutoff = params.get('cutoff') ?? ''
  const cutoff = TIME_RE.test(rawCutoff) ? rawCutoff : (meta?.default_cutoff_local ?? '09:50')

  const update = useCallback(
    (next: { date?: string; cutoff?: string }) => {
      setParams(
        (prev) => {
          const p = new URLSearchParams(prev)
          if (next.date) p.set('date', next.date)
          if (next.cutoff) p.set('cutoff', next.cutoff)
          return p
        },
        { replace: true },
      )
    },
    [setParams],
  )
  return { date, cutoff, first, last, update }
}

export function DecisionPage() {
  const meta = useMeta()
  const { date, cutoff, first, last, update } = useDecisionParams(meta.data)
  const forecast = useForecast(date, cutoff)

  return (
    <>
      <div className="page-head">
        <h1>Day-ahead decision</h1>
        <p>Forecast available at gate closure for the selected delivery day.</p>
      </div>

      <div className="controls">
        <label className="field" htmlFor="decision-date">
          Decision day
          <input
            id="decision-date"
            type="date"
            value={date ?? ''}
            min={first}
            max={last}
            disabled={!date}
            onChange={(e) => {
              if (DATE_RE.test(e.target.value)) update({ date: e.target.value })
            }}
          />
        </label>
        <div className="btn-group" role="group" aria-label="Change day">
          <button
            className="btn"
            type="button"
            disabled={!date || !first || date <= first}
            onClick={() => date && update({ date: addDays(date, -1) })}
          >
            Previous
          </button>
          <button
            className="btn"
            type="button"
            disabled={!date || !last || date >= last}
            onClick={() => date && update({ date: addDays(date, 1) })}
          >
            Next
          </button>
        </div>
        <CutoffField value={cutoff} onChange={(c) => update({ cutoff: c })} />
        {date ? (
          <span className="field">
            Delivery day
            <span className="field-static">{ukDate(addDays(date, 1))}</span>
          </span>
        ) : null}
      </div>

      {meta.isError ? <ErrorState error={meta.error} /> : null}
      {forecast.isPending && !meta.isError ? <LoadingState label="Loading forecast" /> : null}
      {forecast.isError ? <ErrorState error={forecast.error} /> : null}
      {forecast.data ? <DecisionContent view={forecast.data} /> : null}
    </>
  )
}

function DecisionContent({ view }: { view: DecisionView }) {
  const [showBand, setShowBand] = useState(true)
  const [showEarlier, setShowEarlier] = useState(false)
  const [showLater, setShowLater] = useState(false)
  const [demandText, setDemandText] = useState('')

  const selected = view.selected_issue
  const peak = selected ? extreme(selected.points, 'max') : undefined
  const trough = selected ? extreme(selected.points, 'min') : undefined
  const forecastEnergy = selected ? selected.points.reduce((s, p) => s + p.generation_mw, 0) : 0
  const earlierCount = view.issues.filter(
    (i) => i.available_at_cutoff && i.issue_time !== selected?.issue_time && i.coverage_hours > 0,
  ).length
  const laterCount = view.issues.filter(
    (i) => !i.available_at_cutoff && i.coverage_hours > 0,
  ).length
  const hasBand = view.band.length > 0
  const demand = Number(demandText)
  const demandValid = demandText !== '' && Number.isFinite(demand) && demand > 0
  const skill = view.baseline?.skill_score

  return (
    <>
      <section className="card" aria-labelledby="basis-title">
        <div className="card-head">
          <h2 id="basis-title">Decision basis</h2>
        </div>
        <AsOfPanel view={view} />
        <IssueTimeline view={view} />
      </section>

      {view.notes.map((note) => (
        <Callout key={note} kind="warn">
          {note}
        </Callout>
      ))}

      {selected ? (
        <div className="kpi-row">
          <StatTile label="Forecast energy" value={fmtInt(forecastEnergy)} unit="MWh" />
          {hasBand && view.dependable_energy_mwh !== null ? (
            <StatTile
              label="Dependable energy (P90)"
              value={fmtInt(view.dependable_energy_mwh)}
              unit="MWh"
              hint={`${fmtPct((view.dependable_energy_mwh / forecastEnergy) * 100)} of forecast`}
            />
          ) : null}
          <StatTile
            label="Peak hour"
            value={peak ? fmtInt(peak.generation_mw) : '—'}
            unit="MW"
            hint={peak ? `from ${ukTime(peak.target_time)}` : undefined}
          />
          <StatTile
            label="Minimum hour"
            value={trough ? fmtInt(trough.generation_mw) : '—'}
            unit="MW"
            hint={trough ? `from ${ukTime(trough.target_time)}` : undefined}
          />
          {view.summary && view.energy ? (
            <>
              <StatTile label="Metered energy" value={fmtInt(view.energy.actual_mwh)} unit="MWh" />
              <StatTile
                label="Energy error"
                value={fmtSignedMWh(view.energy.error_mwh).replace(' MWh', '')}
                unit="MWh"
                tone={view.energy.error_mwh >= 0 ? 'over' : 'under'}
                hint={
                  view.energy.actual_mwh > 0
                    ? `${fmtPct((view.energy.error_mwh / view.energy.actual_mwh) * 100)} of metered`
                    : undefined
                }
              />
              <StatTile
                label="Mean hourly error"
                value={fmtSignedMW(view.summary.bias_mw).replace(' MW', '')}
                unit="MW"
                tone={view.summary.bias_mw >= 0 ? 'over' : 'under'}
                hint={`MAE ${fmtMW(view.summary.mae_mw)}`}
              />
            </>
          ) : null}
          {skill !== null && skill !== undefined && view.baseline ? (
            <StatTile
              label="Skill vs persistence"
              value={fmtPct(skill * 100)}
              hint={`persistence MAE ${fmtMW(view.baseline.mae_mw)}`}
            />
          ) : null}
        </div>
      ) : null}

      <section className="card" aria-labelledby="chart-title">
        <div className="card-head">
          <div>
            <h2 id="chart-title">Forecast vs outturn, {ukDate(view.delivery_date)}</h2>
            <p>
              Hourly MW.{' '}
              {hasBand && view.calibration
                ? `Band calibrated on the ${view.calibration.days_used} completed days before the decision day.`
                : 'No calibrated band for this day.'}
            </p>
          </div>
          <div className="btn-group">
            <label className="toggle">
              <input
                type="checkbox"
                checked={showBand}
                disabled={!hasBand}
                onChange={(e) => setShowBand(e.target.checked)}
              />
              Band
            </label>
            <label className="toggle">
              <input
                type="checkbox"
                checked={showEarlier}
                disabled={earlierCount === 0}
                onChange={(e) => setShowEarlier(e.target.checked)}
              />
              Earlier issues ({earlierCount})
            </label>
            <label className="toggle">
              <input
                type="checkbox"
                checked={showLater}
                disabled={laterCount === 0}
                onChange={(e) => setShowLater(e.target.checked)}
              />
              Later issues ({laterCount})
            </label>
          </div>
        </div>
        <ForecastVsActualChart
          view={view}
          showBand={showBand}
          showEarlier={showEarlier}
          showLater={showLater}
        />
      </section>

      {hasBand ? (
        <section className="card" aria-labelledby="planner-title">
          <div className="card-head">
            <div>
              <h2 id="planner-title">Procurement planner</h2>
              <p>Volume to buy above wind for the delivery day at a given demand.</p>
            </div>
          </div>
          <Planner
            view={view}
            demandText={demandText}
            onDemand={setDemandText}
            valid={demandValid}
          />
        </section>
      ) : null}

      <section className="card" aria-labelledby="table-title">
        <div className="card-head">
          <h2 id="table-title">Hourly values</h2>
          <p>Error is forecast minus outturn. SP is the settlement period.</p>
        </div>
        <HourlyTable view={view} demand={demandValid ? demand : null} />
      </section>
    </>
  )
}

function Planner({
  view,
  demandText,
  onDemand,
  valid,
}: {
  view: DecisionView
  demandText: string
  onDemand: (v: string) => void
  valid: boolean
}) {
  const demand = Number(demandText)
  const total = (pick: (b: DecisionView['band'][number]) => number) =>
    valid ? view.band.reduce((s, b) => s + Math.max(0, demand - pick(b)), 0) : null
  const buyRaw = total((b) => b.forecast_mw)
  const buyExpected = total((b) => b.expected_mw)
  const buyDependable = total((b) => b.dependable_mw)
  return (
    <div className="planner">
      <label className="field" htmlFor="demand">
        Demand to serve (MW)
        <input
          id="demand"
          type="number"
          inputMode="numeric"
          min={0}
          step={100}
          placeholder="e.g. 8000"
          value={demandText}
          onChange={(e) => onDemand(e.target.value)}
        />
      </label>
      <div className="planner-out">
        <span className="stat-label">On raw forecast</span>
        <span className="stat-value">{buyRaw === null ? '—' : `${fmtInt(buyRaw)} MWh`}</span>
      </div>
      <div className="planner-out">
        <span className="stat-label">On P50 (bias-corrected)</span>
        <span className="stat-value">
          {buyExpected === null ? '—' : `${fmtInt(buyExpected)} MWh`}
        </span>
      </div>
      <div className="planner-out">
        <span className="stat-label">On P90 (90% cover)</span>
        <span className="stat-value pos">
          {buyDependable === null ? '—' : `${fmtInt(buyDependable)} MWh`}
        </span>
        {buyRaw !== null && buyDependable !== null ? (
          <span className="stat-hint">{fmtInt(buyDependable - buyRaw)} MWh above raw forecast</span>
        ) : null}
      </div>
    </div>
  )
}

function HourlyTable({ view, demand }: { view: DecisionView; demand: number | null }) {
  const forecastByTime = new Map(
    view.selected_issue?.points.map((p) => [p.target_time, p.generation_mw]),
  )
  const bandByTime = new Map(view.band.map((b) => [b.target_time, b]))
  const actualByTime = new Map(view.actuals_hourly.map((h) => [h.target_time, h]))
  const times = view.actuals_hourly.length
    ? view.actuals_hourly.map((h) => h.target_time)
    : (view.selected_issue?.points ?? []).map((p) => p.target_time)
  const hasBand = view.band.length > 0
  const showBuy = demand !== null && hasBand
  if (times.length === 0) return <p className="muted">No data for this day.</p>

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">Hour (UK)</th>
            <th scope="col">SP</th>
            <th scope="col">Forecast MW</th>
            {hasBand ? <th scope="col">Dependable MW</th> : null}
            <th scope="col">Outturn MW</th>
            <th scope="col">Error MW</th>
            {showBuy ? <th scope="col">Buy MW</th> : null}
          </tr>
        </thead>
        <tbody>
          {times.map((time, index) => {
            const f = forecastByTime.get(time) ?? null
            const a = actualByTime.get(time)
            const incomplete = a ? !a.is_complete : false
            const error = f !== null && a && !incomplete ? f - a.generation_mw : null
            const band = bandByTime.get(time)
            return (
              <tr key={time} className={incomplete ? 'incomplete' : undefined}>
                <td className="mono">
                  {ukTime(time)}
                  {incomplete ? ' (partial)' : ''}
                </td>
                <td className="num muted">
                  {index * 2 + 1}-{index * 2 + 2}
                </td>
                <td className="num">{f === null ? '—' : fmtInt(f)}</td>
                {hasBand ? (
                  <td className="num">{band ? fmtInt(band.dependable_mw) : '—'}</td>
                ) : null}
                <td className="num">{a ? fmtInt(a.generation_mw) : '—'}</td>
                <td className={`num ${error === null ? '' : error >= 0 ? 'pos' : 'neg'}`}>
                  {error === null ? '—' : fmtSignedMW(error).replace(' MW', '')}
                </td>
                {showBuy ? (
                  <td className="num">
                    {band ? fmtInt(Math.max(0, demand - band.dependable_mw)) : '—'}
                  </td>
                ) : null}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function extreme<T extends { generation_mw: number }>(
  points: T[],
  kind: 'max' | 'min',
): T | undefined {
  return points.reduce<T | undefined>((best, p) => {
    if (!best) return p
    const better =
      kind === 'max' ? p.generation_mw > best.generation_mw : p.generation_mw < best.generation_mw
    return better ? p : best
  }, undefined)
}
