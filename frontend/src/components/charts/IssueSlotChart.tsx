import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { IssueSlot } from '../../api/client'
import { fmtCompact, fmtMW, fmtSignedMW } from '../../lib/format'
import { useChartTheme } from '../../lib/useChartTheme'
import { Legend } from '../Legend'
import { ChartTooltip } from './ChartTooltip'
import { CHART_MARGIN, axisProps, firstPayload, gridProps, type TooltipRenderProps } from './common'

interface Row {
  slot: string
  available: boolean
  mae: number
  bias: number
  days: number
}

interface Props {
  slots: IssueSlot[]
  cutoff: string
}

export function IssueSlotChart({ slots, cutoff }: Props) {
  const theme = useChartTheme()
  const rows: Row[] = slots.map((s) => ({
    slot: s.slot_label,
    available: s.available_at_cutoff,
    mae: s.summary.mae_mw,
    bias: s.summary.bias_mw,
    days: s.days,
  }))

  const renderTooltip = (props: TooltipRenderProps<Row>) => {
    const r = firstPayload(props)
    if (!r) return null
    return (
      <ChartTooltip
        title={`Issue published ${r.slot}`}
        rows={[
          { label: 'Mean absolute error', value: fmtMW(r.mae) },
          { label: 'Mean error (bias)', value: fmtSignedMW(r.bias) },
          { label: 'Days with this slot', value: String(r.days) },
        ]}
        footer={
          r.available
            ? `Available before the ${cutoff} cutoff`
            : `Published after the ${cutoff} cutoff`
        }
      />
    )
  }

  return (
    <div>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={rows} margin={CHART_MARGIN} barCategoryGap={2}>
          <CartesianGrid {...gridProps(theme)} />
          <XAxis dataKey="slot" {...axisProps(theme)} interval={0} />
          <YAxis {...axisProps(theme)} tickFormatter={fmtCompact} width={44} domain={[0, 'auto']} />
          <Tooltip content={renderTooltip} cursor={{ fill: theme.gap }} isAnimationActive={false} />
          <Bar dataKey="mae" isAnimationActive={false} maxBarSize={24} radius={[4, 4, 0, 0]}>
            {rows.map((r) => (
              <Cell key={r.slot} fill={r.available ? theme.forecast : theme.deemph} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <Legend
        items={[
          { label: `Available before ${cutoff} cutoff`, color: theme.forecast, shape: 'box' },
          { label: 'Published after cutoff', color: theme.deemph, shape: 'box' },
        ]}
      />
    </div>
  )
}
