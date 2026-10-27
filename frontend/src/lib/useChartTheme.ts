export interface ChartTheme {
  forecast: string
  actual: string
  deemph: string
  over: string
  under: string
  band: string
  gap: string
  grid: string
  axis: string
  ink: string
  ink2: string
  muted: string
  surface: string
}

const THEME: ChartTheme = {
  forecast: '#2563eb',
  actual: '#ea580c',
  deemph: '#9ca3af',
  over: '#dc2626',
  under: '#2563eb',
  band: 'rgba(37, 99, 235, 0.12)',
  gap: 'rgba(17, 24, 39, 0.08)',
  grid: '#e5e7eb',
  axis: '#cbd5e1',
  ink: '#111827',
  ink2: '#374151',
  muted: '#4b5563',
  surface: '#ffffff',
}

export function useChartTheme(): ChartTheme {
  return THEME
}
