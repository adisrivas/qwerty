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
import type { DailyAccuracy } from '../../api/client'
import { fmtCompact, fmtMW, fmtSignedMW, ukDayLabel, ukShortDate } from '../../lib/format'
import { useChartTheme } from '../../lib/useChartTheme'
import { Legend } from '../Legend'
import { ChartTooltip } from './ChartTooltip'
import { CHART_MARGIN, axisProps, firstPayload, gridProps, type TooltipRenderProps } from './common'

interface Row {
  decisionDate: string
  deliveryDate: string
  label: string
  bias: number | null
  mae: number | null
  p90: number | null
  hours: number
}

interface Props {
  daily: DailyAccuracy[]
  onSelectDay?: ((decisionDate: string) => void) | undefined
}

export function DailyBiasChart({ daily, onSelectDay }: Props) {
  const theme = useChartTheme()
  const rows: Row[] = daily.map((d) => ({
    decisionDate: d.decision_date,
    deliveryDate: d.delivery_date,
    label: ukDayLabel(d.delivery_date),
    bias: d.summary?.bias_mw ?? null,
    mae: d.summary?.mae_mw ?? null,
    p90: d.summary?.p90_mw ?? null,
    hours: d.hours_compared,
  }))

  const renderTooltip = (props: TooltipRenderProps<Row>) => {
    const r = firstPayload(props)
    if (!r) return null
    return (
      <ChartTooltip
        title={`Delivery ${ukShortDate(r.deliveryDate)} (decided ${ukShortDate(r.decisionDate)})`}
        rows={[
          { label: 'Mean error (bias)', value: r.bias === null ? 'n/a' : fmtSignedMW(r.bias) },
          { label: 'Mean absolute error', value: r.mae === null ? 'n/a' : fmtMW(r.mae) },
          { label: 'P90 error', value: r.p90 === null ? 'n/a' : fmtSignedMW(r.p90) },
          { label: 'Hours compared', value: String(r.hours) },
        ]}
        footer={onSelectDay ? 'Select to open the decision view' : undefined}
      />
    )
  }

  return (
    <div>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={rows} margin={CHART_MARGIN} barCategoryGap={2}>
          <CartesianGrid {...gridProps(theme)} />
          <XAxis dataKey="label" {...axisProps(theme)} interval={2} />
          <YAxis {...axisProps(theme)} tickFormatter={fmtCompact} width={44} />
          <Tooltip content={renderTooltip} cursor={{ fill: theme.gap }} isAnimationActive={false} />
          <ReferenceLine y={0} stroke={theme.axis} />
          <Bar
            dataKey="bias"
            isAnimationActive={false}
            maxBarSize={24}
            onClick={(_, index) => {
              const r = rows[index]
              if (r && onSelectDay) onSelectDay(r.decisionDate)
            }}
            cursor={onSelectDay ? 'pointer' : undefined}
          >
            {rows.map((r) => (
              <Cell key={r.decisionDate} fill={(r.bias ?? 0) >= 0 ? theme.over : theme.under} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <Legend
        items={[
          {
            label: 'Forecast above outturn (under-delivery)',
            color: theme.over,
            shape: 'box',
          },
          { label: 'Forecast below outturn (over-delivery)', color: theme.under, shape: 'box' },
        ]}
      />
    </div>
  )
}
