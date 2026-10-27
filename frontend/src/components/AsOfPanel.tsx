import type { DecisionView } from '../api/client'
import { fmtMinutes, ukDate, ukDateTime } from '../lib/format'

export function AsOfPanel({ view }: { view: DecisionView }) {
  const sel = view.selected_issue
  const earlier = view.issues.filter(
    (i) => i.available_at_cutoff && i.issue_time !== sel?.issue_time && i.coverage_hours > 0,
  ).length
  const later = view.issues.filter((i) => !i.available_at_cutoff && i.coverage_hours > 0).length
  const leadHours = sel
    ? Math.round((Date.parse(view.delivery_window.start) - Date.parse(sel.issue_time)) / 3600000)
    : null

  if (!sel) {
    return (
      <div className="asof asof-missing" role="alert">
        <span className="asof-tag">No forecast available at cutoff</span>
        <p>
          No WINDFOR issue covering {ukDate(view.delivery_date)} was published by{' '}
          {view.cutoff_local} on {ukDate(view.decision_date)}. Select a later cutoff to view the
          next issue.
        </p>
      </div>
    )
  }

  return (
    <dl className="asof">
      <div>
        <dt>Forecast issue</dt>
        <dd className="mono">{ukDateTime(sel.issue_time)}</dd>
        <small>WINDFOR publication, UK time</small>
      </div>
      <div>
        <dt>Age at cutoff</dt>
        <dd className="mono">{fmtMinutes(sel.minutes_before_cutoff)}</dd>
        <small>before {view.cutoff_local} gate closure</small>
      </div>
      <div>
        <dt>Lead time</dt>
        <dd className="mono">{leadHours ?? '—'} h</dd>
        <small>to start of delivery day</small>
      </div>
      <div>
        <dt>Coverage</dt>
        <dd className="mono">{sel.coverage_hours} / 24 h</dd>
        <small>of {ukDate(view.delivery_date)}</small>
      </div>
      <div>
        <dt>Other issues</dt>
        <dd className="mono">
          {earlier} <span className="muted">earlier</span> · {later}{' '}
          <span className="muted">later</span>
        </dd>
        <small>covering the delivery day</small>
      </div>
    </dl>
  )
}
