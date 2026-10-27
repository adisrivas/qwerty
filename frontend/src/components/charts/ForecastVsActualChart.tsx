import { useMemo } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { DecisionView, Issue } from '../../api/client'
import { fmtCompact, fmtMW, fmtSignedMW, ukTime } from '../../lib/format'
import { useChartTheme } from '../../lib/useChartTheme'
import { Legend } from '../Legend'
import { ChartTooltip } from './ChartTooltip'
import { CHART_MARGIN, axisProps, firstPayload, gridProps, type TooltipRenderProps } from './common'

interface Row {
  time: string
  hour: string
  forecast: number | null
  actual: number | null
  actualIncomplete: boolean
  gap: [number, number] | null
  band: [number, number] | null
  dependable: number | null
  others: Record<string, number>
}

interface Props {
  view: DecisionView
  showBand: boolean
  showEarlier: boolean
  showLater: boolean
}

function issueKey(issue: Issue): string {
  return `issue_${issue.issue_time}`
}

export function ForecastVsActualChart({ view, showBand, showEarlier, showLater }: Props) {
  const theme = useChartTheme()

  const { rows, earlier, later } = useMemo(() => {
    const selectedTime = view.selected_issue?.issue_time
    const context = view.issues.filter((i) => i.issue_time !== selectedTime && i.coverage_hours > 0)
    const earlierIssues = context.filter((i) => i.available_at_cutoff)
    const laterIssues = context.filter((i) => !i.available_at_cutoff)

    const byTime = new Map<string, Row>()
    const row = (time: string): Row => {
      let r = byTime.get(time)
      if (!r) {
        r = {
          time,
          hour: ukTime(time),
          forecast: null,
          actual: null,
          actualIncomplete: false,
          gap: null,
          band: null,
          dependable: null,
          others: {},
        }
        byTime.set(time, r)
      }
      return r
    }
    for (const p of view.selected_issue?.points ?? []) row(p.target_time).forecast = p.generation_mw
    for (const b of view.band) {
      const r = row(b.target_time)
      r.band = [b.dependable_mw, b.optimistic_mw]
      r.dependable = b.dependable_mw
    }
    for (const h of view.actuals_hourly) {
      const r = row(h.target_time)
      r.actual = h.generation_mw
      r.actualIncomplete = !h.is_complete
    }
    for (const issue of context) {
      for (const p of issue.points) row(p.target_time).others[issueKey(issue)] = p.generation_mw
    }
    const ordered = [...byTime.values()].sort((a, b) => a.time.localeCompare(b.time))
    for (const r of ordered) {
      if (r.forecast !== null && r.actual !== null && !r.actualIncomplete) {
        r.gap = [Math.min(r.forecast, r.actual), Math.max(r.forecast, r.actual)]
      }
    }
    return { rows: ordered, earlier: earlierIssues, later: laterIssues }
  }, [view])

  const hasActual = view.actuals_hourly.length > 0
  const hasBand = showBand && view.band.length > 0
  const legend = [
    { label: 'Forecast at cutoff', color: theme.forecast },
    ...(hasBand ? [{ label: 'Dependable wind (P90)', color: theme.forecast, dashed: true }] : []),
    ...(hasBand
      ? [{ label: 'Calibrated P10 to P90 band', color: theme.band, shape: 'box' as const }]
      : []),
    ...(hasActual ? [{ label: 'Actual (hourly mean)', color: theme.actual }] : []),
    ...(showEarlier && earlier.length ? [{ label: 'Earlier issues', color: theme.deemph }] : []),
    ...(showLater && later.length
      ? [{ label: 'Later issues (after cutoff)', color: theme.deemph, dashed: true }]
      : []),
  ]

  const renderTooltip = (props: TooltipRenderProps<Row>) => {
    const r = firstPayload(props)
    if (!r) return null
    const tooltipRows = []
    if (r.forecast !== null)
      tooltipRows.push({ label: 'Forecast', value: fmtMW(r.forecast), color: theme.forecast })
    if (hasBand && r.dependable !== null)
      tooltipRows.push({ label: 'Dependable (P90)', value: fmtMW(r.dependable) })
    if (r.actual !== null)
      tooltipRows.push({
        label: r.actualIncomplete ? 'Actual (incomplete hour)' : 'Actual',
        value: fmtMW(r.actual),
        color: theme.actual,
      })
    if (r.forecast !== null && r.actual !== null && !r.actualIncomplete)
      tooltipRows.push({
        label: 'Error (forecast minus actual)',
        value: fmtSignedMW(r.forecast - r.actual),
      })
    return <ChartTooltip title={`${r.hour} UK time`} rows={tooltipRows} />
  }

  return (
    <div>
      <ResponsiveContainer width="100%" height={340}>
        <ComposedChart data={rows} margin={CHART_MARGIN}>
          <CartesianGrid {...gridProps(theme)} />
          <XAxis dataKey="hour" {...axisProps(theme)} interval={2} />
          <YAxis {...axisProps(theme)} tickFormatter={fmtCompact} width={44} domain={[0, 'auto']} />
          <Tooltip
            content={renderTooltip}
            cursor={{ stroke: theme.axis }}
            isAnimationActive={false}
          />
          <ReferenceLine y={0} stroke={theme.axis} />
          {hasBand ? (
            <Area
              dataKey="band"
              stroke="none"
              fill={theme.band}
              fillOpacity={1}
              isAnimationActive={false}
              connectNulls={false}
              legendType="none"
              activeDot={false}
            />
          ) : null}
          {showEarlier &&
            earlier.map((issue) => (
              <Line
                key={issue.issue_time}
                dataKey={(d: Row) => d.others[issueKey(issue)] ?? null}
                stroke={theme.deemph}
                strokeWidth={1}
                dot={false}
                isAnimationActive={false}
                connectNulls={false}
                legendType="none"
              />
            ))}
          {showLater &&
            later.map((issue) => (
              <Line
                key={issue.issue_time}
                dataKey={(d: Row) => d.others[issueKey(issue)] ?? null}
                stroke={theme.deemph}
                strokeWidth={1}
                strokeDasharray="4 3"
                dot={false}
                isAnimationActive={false}
                connectNulls={false}
                legendType="none"
              />
            ))}
          {hasActual ? (
            <Area
              dataKey="gap"
              stroke="none"
              fill={theme.gap}
              fillOpacity={1}
              isAnimationActive={false}
              connectNulls={false}
              legendType="none"
              activeDot={false}
            />
          ) : null}
          {hasBand ? (
            <Line
              dataKey="dependable"
              stroke={theme.forecast}
              strokeWidth={1.5}
              strokeDasharray="5 3"
              dot={false}
              isAnimationActive={false}
              legendType="none"
            />
          ) : null}
          <Line
            dataKey="forecast"
            stroke={theme.forecast}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, stroke: theme.surface, strokeWidth: 2 }}
            isAnimationActive={false}
          />
          {hasActual ? (
            <Line
              dataKey="actual"
              stroke={theme.actual}
              strokeWidth={2}
              dot={{ r: 3, fill: theme.actual, stroke: theme.surface, strokeWidth: 2 }}
              activeDot={{ r: 4, stroke: theme.surface, strokeWidth: 2 }}
              isAnimationActive={false}
            />
          ) : null}
        </ComposedChart>
      </ResponsiveContainer>
      <Legend items={legend} />
    </div>
  )
}
