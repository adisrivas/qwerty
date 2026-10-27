import type { ChartTheme } from '../../lib/useChartTheme'

export function axisProps(theme: ChartTheme) {
  return {
    tick: { fill: theme.muted, fontSize: 12 },
    axisLine: { stroke: theme.axis },
    tickLine: false as const,
  }
}

export function gridProps(theme: ChartTheme) {
  return { stroke: theme.grid, vertical: false as const }
}

export const CHART_MARGIN = { top: 12, right: 16, bottom: 4, left: 0 }

export interface TooltipPayloadItem<T> {
  payload?: T
}
export interface TooltipRenderProps<T> {
  active?: boolean
  payload?: ReadonlyArray<TooltipPayloadItem<T>>
}

export function firstPayload<T>(props: TooltipRenderProps<T>): T | undefined {
  if (!props.active || !props.payload || props.payload.length === 0) return undefined
  return props.payload[0]?.payload
}
