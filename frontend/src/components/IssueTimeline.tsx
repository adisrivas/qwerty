import { useId } from 'react'
import type { DecisionView, Issue } from '../api/client'
import { fmtMinutes, ukTime } from '../lib/format'
import { useChartTheme } from '../lib/useChartTheme'

interface Props {
  view: DecisionView
}

const W = 1000
const H = 104
const PAD_X = 28
const AXIS_Y = 56

function localMinutes(iso: string): number {
  const [h, m] = ukTime(iso).split(':').map(Number)
  return (h ?? 0) * 60 + (m ?? 0)
}

function x(minutes: number): number {
  return PAD_X + (minutes / 1440) * (W - 2 * PAD_X)
}

function ukDay(iso: string): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London' }).format(new Date(iso))
}

export function IssueTimeline({ view }: Props) {
  const theme = useChartTheme()
  const titleId = useId()
  const decisionDay = ukDay(view.cutoff_utc)
  const issues = view.issues.filter((i: Issue) => ukDay(i.issue_time) === decisionDay)
  const selected = view.selected_issue?.issue_time
  const [ch, cm] = view.cutoff_local.split(':').map(Number)
  const cutoffMin = (ch ?? 0) * 60 + (cm ?? 0)
  const ticks = [0, 3, 6, 9, 12, 15, 18, 21, 24]

  return (
    <figure className="timeline" aria-labelledby={titleId}>
      <figcaption id={titleId} className="timeline-caption">
        WINDFOR issues published on the decision day. Cutoff {view.cutoff_local} UK time.
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Forecast issues against the cutoff">
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={x(t * 60)}
              x2={x(t * 60)}
              y1={AXIS_Y - 4}
              y2={AXIS_Y + 4}
              stroke={theme.axis}
              strokeWidth={1}
            />
            <text
              x={x(t * 60)}
              y={AXIS_Y + 20}
              textAnchor="middle"
              fontSize={11}
              fill={theme.muted}
            >
              {String(t).padStart(2, '0')}:00
            </text>
          </g>
        ))}
        <line x1={x(0)} x2={x(1440)} y1={AXIS_Y} y2={AXIS_Y} stroke={theme.axis} strokeWidth={1} />
        <rect
          x={x(0)}
          y={AXIS_Y - 14}
          width={x(cutoffMin) - x(0)}
          height={28}
          fill={theme.forecast}
          opacity={0.08}
        />
        <line
          x1={x(cutoffMin)}
          x2={x(cutoffMin)}
          y1={AXIS_Y - 30}
          y2={AXIS_Y + 10}
          stroke={theme.ink}
          strokeWidth={1.5}
          strokeDasharray="4 3"
        />
        <text
          x={x(cutoffMin)}
          y={AXIS_Y - 36}
          textAnchor="middle"
          fontSize={11}
          fontWeight={600}
          fill={theme.ink}
        >
          gate closure {view.cutoff_local}
        </text>

        {issues.map((issue) => {
          const cx = x(localMinutes(issue.issue_time))
          const isSelected = issue.issue_time === selected
          const usable = issue.available_at_cutoff
          const timing = `${fmtMinutes(issue.minutes_before_cutoff)} ${usable ? 'before' : 'after'} cutoff`
          return (
            <g key={issue.issue_time}>
              <title>
                {`Issue ${ukTime(issue.issue_time)}. ${timing}. Covers ${issue.coverage_hours} h of the delivery day${isSelected ? '. Selected' : ''}.`}
              </title>
              <circle
                cx={cx}
                cy={AXIS_Y}
                r={isSelected ? 8 : 5}
                fill={usable ? theme.forecast : theme.deemph}
                stroke={theme.surface}
                strokeWidth={2}
              />
              {isSelected ? (
                <text
                  x={cx}
                  y={AXIS_Y + 36}
                  textAnchor="middle"
                  fontSize={11}
                  fontWeight={600}
                  fill={theme.ink}
                >
                  selected {ukTime(issue.issue_time)}
                </text>
              ) : null}
            </g>
          )
        })}
      </svg>
      <div className="legend">
        <span className="legend-item">
          <span
            className="legend-swatch dot"
            style={{ background: theme.forecast }}
            aria-hidden="true"
          />
          Published before cutoff
        </span>
        <span className="legend-item">
          <span
            className="legend-swatch dot"
            style={{ background: theme.deemph }}
            aria-hidden="true"
          />
          Published after cutoff
        </span>
      </div>
    </figure>
  )
}
