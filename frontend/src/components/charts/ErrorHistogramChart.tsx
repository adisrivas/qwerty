import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { AccuracyReport } from '../../api/client'
import { fmtCompact, fmtSignedMW } from '../../lib/format'
import { useChartTheme } from '../../lib/useChartTheme'
import { Legend } from '../Legend'
import { ChartTooltip } from './ChartTooltip'
import { CHART_MARGIN, axisProps, firstPayload, gridProps, type TooltipRenderProps } from './common'

interface Row {
  lower: number
  upper: number
  mid: number
  label: string
  count: number
  share: number
}

export function ErrorHistogramChart({ report }: { report: AccuracyReport }) {
  const theme = useChartTheme()
  const total = report.hours_compared || 1
  const rows: Row[] = report.histogram.bins.map((b) => ({
    lower: b.lower_mw,
    upper: b.upper_mw,
    mid: (b.lower_mw + b.upper_mw) / 2,
    label: fmtCompact(b.lower_mw),
    count: b.count,
    share: (b.count / total) * 100,
  }))

  const renderTooltip = (props: TooltipRenderProps<Row>) => {
    const r = firstPayload(props)
    if (!r) return null
    return (
      <ChartTooltip
        title={`${fmtSignedMW(r.lower)} to ${fmtSignedMW(r.upper)}`}
        rows={[
          { label: 'Hours', value: String(r.count) },
          { label: 'Share of hours', value: `${r.share.toFixed(1)}%` },
        ]}
      />
    )
  }

  const p90Label = rows.find(
    (r) => r.lower <= report.overall.p90_mw && report.overall.p90_mw < r.upper,
  )

  return (
    <div>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={rows} margin={{ ...CHART_MARGIN, top: 24 }} barCategoryGap={2}>
          <CartesianGrid {...gridProps(theme)} />
          <XAxis
            dataKey="label"
            {...axisProps(theme)}
            interval={1}
            label={{
              value: 'Error, MW (bin start)',
              position: 'insideBottom',
              dy: 10,
              fill: theme.muted,
              fontSize: 12,
            }}
            height={52}
          />
          <YAxis {...axisProps(theme)} width={36} allowDecimals={false} />
          <Tooltip content={renderTooltip} cursor={{ fill: theme.gap }} isAnimationActive={false} />
          {p90Label ? (
            <ReferenceLine
              x={p90Label.label}
              stroke={theme.ink2}
              strokeDasharray="4 3"
              label={{ value: 'P90', position: 'top', fill: theme.ink2, fontSize: 12 }}
            />
          ) : null}
          <Bar dataKey="count" isAnimationActive={false} maxBarSize={24} radius={[4, 4, 0, 0]}>
            {rows.map((r) => (
              <Cell key={r.lower} fill={r.lower >= 0 ? theme.over : theme.under} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <Legend
        items={[
          { label: 'Forecast above outturn', color: theme.over, shape: 'box' },
          { label: 'Forecast below outturn', color: theme.under, shape: 'box' },
        ]}
      />
    </div>
  )
}
