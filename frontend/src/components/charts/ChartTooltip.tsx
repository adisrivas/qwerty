import type { ReactNode } from 'react'

export interface TooltipRow {
  label: string
  value: string
  color?: string | undefined
}

interface ChartTooltipProps {
  title: ReactNode
  rows: TooltipRow[]
  footer?: ReactNode
}

export function ChartTooltip({ title, rows, footer }: ChartTooltipProps) {
  return (
    <div className="tip" role="presentation">
      <div className="tip-title">{title}</div>
      {rows.map((row) => (
        <div className="tip-row" key={row.label}>
          <span>
            {row.color ? (
              <span
                className="legend-swatch box"
                style={{ background: row.color }}
                aria-hidden="true"
              />
            ) : null}
            {row.label}
          </span>
          <span className="tabular">{row.value}</span>
        </div>
      ))}
      {footer ? (
        <div className="muted" style={{ marginTop: 4 }}>
          {footer}
        </div>
      ) : null}
    </div>
  )
}
