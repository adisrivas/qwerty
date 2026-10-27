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
import type { ForecastBand } from '../../api/client'
import { fmtCompact, fmtMW, fmtPct, fmtSignedMW } from '../../lib/format'
import { useChartTheme } from '../../lib/useChartTheme'
import { Legend } from '../Legend'
import { ChartTooltip } from './ChartTooltip'
import { CHART_MARGIN, axisProps, firstPayload, gridProps, type TooltipRenderProps } from './common'

interface Row {
  label: string
  bias: number
  mae: number
  nmae: number
  count: number
}

export function ForecastBandChart({ bands }: { bands: ForecastBand[] }) {
  const theme = useChartTheme()
  const rows: Row[] = bands.map((b) => ({
    label: b.label,
    bias: b.summary.bias_mw,
    mae: b.summary.mae_mw,
    nmae: b.summary.nmae_pct,
    count: b.summary.count,
  }))

  const renderTooltip = (props: TooltipRenderProps<Row>) => {
    const r = firstPayload(props)
    if (!r) return null
    return (
      <ChartTooltip
        title={`Forecast ${r.label}`}
        rows={[
          { label: 'Mean error (bias)', value: fmtSignedMW(r.bias) },
          { label: 'Mean absolute error', value: fmtMW(r.mae) },
          { label: 'MAE, % of mean outturn', value: fmtPct(r.nmae) },
          { label: 'Hours', value: String(r.count) },
        ]}
      />
    )
  }

  return (
    <div>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={rows} margin={CHART_MARGIN} barCategoryGap={8}>
          <CartesianGrid {...gridProps(theme)} />
          <XAxis dataKey="label" {...axisProps(theme)} interval={0} />
          <YAxis {...axisProps(theme)} tickFormatter={fmtCompact} width={44} />
          <Tooltip content={renderTooltip} cursor={{ fill: theme.gap }} isAnimationActive={false} />
          <ReferenceLine y={0} stroke={theme.axis} />
          <Bar dataKey="bias" isAnimationActive={false} maxBarSize={48}>
            {rows.map((r) => (
              <Cell key={r.label} fill={r.bias >= 0 ? theme.over : theme.under} />
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
