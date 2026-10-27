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
import type { HourOfDay } from '../../api/client'
import { fmtCompact, fmtMW, fmtSignedMW } from '../../lib/format'
import { useChartTheme } from '../../lib/useChartTheme'
import { Legend } from '../Legend'
import { ChartTooltip } from './ChartTooltip'
import { CHART_MARGIN, axisProps, firstPayload, gridProps, type TooltipRenderProps } from './common'

interface Row {
  hour: number
  label: string
  bias: number
  mae: number
  rmse: number
  count: number
}

export function HourOfDayChart({ hours }: { hours: HourOfDay[] }) {
  const theme = useChartTheme()
  const rows: Row[] = hours.map((h) => ({
    hour: h.hour,
    label: `${String(h.hour).padStart(2, '0')}:00`,
    bias: h.summary.bias_mw,
    mae: h.summary.mae_mw,
    rmse: h.summary.rmse_mw,
    count: h.summary.count,
  }))

  const renderTooltip = (props: TooltipRenderProps<Row>) => {
    const r = firstPayload(props)
    if (!r) return null
    return (
      <ChartTooltip
        title={`Hour starting ${r.label} UK time`}
        rows={[
          { label: 'Mean error (bias)', value: fmtSignedMW(r.bias) },
          { label: 'Mean absolute error', value: fmtMW(r.mae) },
          { label: 'RMSE', value: fmtMW(r.rmse) },
          { label: 'Days', value: String(r.count) },
        ]}
      />
    )
  }

  return (
    <div>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={rows} margin={CHART_MARGIN} barCategoryGap={2}>
          <CartesianGrid {...gridProps(theme)} />
          <XAxis dataKey="label" {...axisProps(theme)} interval={2} />
          <YAxis {...axisProps(theme)} tickFormatter={fmtCompact} width={44} />
          <Tooltip content={renderTooltip} cursor={{ fill: theme.gap }} isAnimationActive={false} />
          <ReferenceLine y={0} stroke={theme.axis} />
          <Bar dataKey="bias" isAnimationActive={false} maxBarSize={24}>
            {rows.map((r) => (
              <Cell key={r.hour} fill={r.bias >= 0 ? theme.over : theme.under} />
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
