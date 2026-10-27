import type { AccuracyReport, DecisionView, ErrorSummary, Meta } from '../api/client'

export const meta: Meta = {
  app_name: 'Day-ahead Wind Forecast',
  version: '0.1.0',
  environment: 'test',
  timezone: 'Europe/London',
  first_decision_date: '2026-01-01',
  last_decision_date: '2026-01-31',
  default_cutoff_local: '09:50',
  calibration_lookback_days: 14,
  calibration_min_days: 5,
  persistence_lag_hours: 48,
  forecast_issue_count: 408,
  actual_point_count: 2304,
  snapshot: {
    created_at: '2026-10-26T06:40:36Z',
    source_base_url: 'https://data.elexon.co.uk/bmrs/api/v1',
    windfor: {
      file: 'windfor.json',
      row_count: 29784,
      sha256: 'abc123def456',
      endpoint: '/datasets/WINDFOR/stream',
      params: {
        publishDateTimeFrom: '2025-12-14T00:00:00Z',
        publishDateTimeTo: '2026-02-03T00:00:00Z',
      },
    },
    fuelhh: {
      file: 'fuelhh_wind.json',
      row_count: 2304,
      sha256: '789abc',
      endpoint: '/datasets/FUELHH/stream',
      params: {
        settlementDateFrom: '2025-12-16',
        settlementDateTo: '2026-02-01',
        fuelType: 'WIND',
      },
    },
    notes: ['note one'],
  },
  assumptions: ['Assumption A', 'Assumption B'],
}

const summary: ErrorSummary = {
  count: 24,
  mean_actual_mw: 7578,
  mean_forecast_mw: 7975,
  bias_mw: 397,
  mae_mw: 859,
  rmse_mw: 1085,
  nmae_pct: 11.3,
  p10_mw: -866,
  p50_mw: 190,
  p90_mw: 1781,
  max_over_forecast_mw: 2576,
  max_under_forecast_mw: -993,
  buffer_p90_mw: 1781,
}

function hours(day: string, base: number, step: number) {
  return Array.from({ length: 24 }, (_, h) => ({
    target_time: `${day}T${String(h).padStart(2, '0')}:00:00Z`,
    generation_mw: base + step * h,
  }))
}

const forecastPoints = hours('2026-01-16', 8000, 50)

export const decisionView: DecisionView = {
  decision_date: '2026-01-15',
  delivery_date: '2026-01-16',
  timezone: 'Europe/London',
  cutoff_local: '09:50',
  cutoff_utc: '2026-01-15T09:50:00Z',
  delivery_window: { start: '2026-01-16T00:00:00Z', end: '2026-01-17T00:00:00Z' },
  selected_issue: {
    issue_time: '2026-01-15T09:30:00Z',
    slot_label: '09:30',
    available_at_cutoff: true,
    minutes_before_cutoff: 20,
    coverage_hours: 24,
    points: forecastPoints,
  },
  issues: [
    {
      issue_time: '2026-01-15T07:30:00Z',
      slot_label: '07:30',
      available_at_cutoff: true,
      minutes_before_cutoff: 140,
      coverage_hours: 24,
      points: hours('2026-01-16', 8200, 50),
    },
    {
      issue_time: '2026-01-15T09:30:00Z',
      slot_label: '09:30',
      available_at_cutoff: true,
      minutes_before_cutoff: 20,
      coverage_hours: 24,
      points: forecastPoints,
    },
    {
      issue_time: '2026-01-15T11:30:00Z',
      slot_label: '11:30',
      available_at_cutoff: false,
      minutes_before_cutoff: -100,
      coverage_hours: 24,
      points: hours('2026-01-16', 7900, 50),
    },
  ],
  calibration: {
    window_from_decision_date: '2025-12-31',
    window_to_decision_date: '2026-01-13',
    days_used: 14,
    hours_used: 336,
    bias_mw: 1808,
    p10_mw: -1038,
    p50_mw: 1404,
    p90_mw: 4777,
  },
  band: forecastPoints.map((p) => ({
    target_time: p.target_time,
    forecast_mw: p.generation_mw,
    dependable_mw: Math.max(0, p.generation_mw - 4777),
    expected_mw: Math.max(0, p.generation_mw - 1404),
    optimistic_mw: p.generation_mw + 1038,
  })),
  dependable_energy_mwh: 76754,
  actuals_half_hourly: [],
  actuals_hourly: hours('2026-01-16', 7600, 50).map((p) => ({
    target_time: p.target_time,
    generation_mw: p.generation_mw,
    periods_used: 2,
    is_complete: true,
  })),
  comparison: forecastPoints.map((p) => ({
    target_time: p.target_time,
    forecast_mw: p.generation_mw,
    actual_mw: p.generation_mw - 400,
    error_mw: 400,
  })),
  summary,
  baseline: { name: 'persistence_48h', hours: 24, mae_mw: 2257, bias_mw: 2092, skill_score: 0.62 },
  energy: { hours: 24, forecast_mwh: 205800, actual_mwh: 196200, error_mwh: 9600 },
  notes: [],
}

export const accuracyReport: AccuracyReport = {
  from_decision_date: '2026-01-01',
  to_decision_date: '2026-01-31',
  timezone: 'Europe/London',
  cutoff_local: '09:50',
  days_requested: 31,
  days_compared: 31,
  days_without_forecast: [],
  hours_compared: 744,
  overall: {
    ...summary,
    count: 744,
    bias_mw: 1730,
    mae_mw: 2013,
    rmse_mw: 2506,
    p90_mw: 4144,
    buffer_p90_mw: 4144,
  },
  baseline: { name: 'persistence_48h', hours: 744, mae_mw: 4340, bias_mw: 336, skill_score: 0.536 },
  guidance: {
    bias_mw: 1730,
    buffer_p90_mw: 4144,
    buffer_p90_pct_of_mean_actual: 36.7,
    coverage_options: [
      { confidence_pct: 50, buffer_mw: 1560, pct_of_mean_actual: 13.8 },
      { confidence_pct: 90, buffer_mw: 4144, pct_of_mean_actual: 36.7 },
      { confidence_pct: 95, buffer_mw: 5322, pct_of_mean_actual: 47.2 },
    ],
    explanation: 'Plan on wind delivering about 4,144 MW less than forecast.',
  },
  band_backtest: {
    target_pct: 90,
    days_checked: 31,
    days_without_history: 0,
    hours_checked: 744,
    hours_covered: 648,
    coverage_pct: 87.1,
  },
  daily: [
    {
      decision_date: '2026-01-01',
      delivery_date: '2026-01-02',
      issue_time: '2026-01-01T09:30:00Z',
      hours_compared: 24,
      summary,
      energy: { hours: 24, forecast_mwh: 1, actual_mwh: 1, error_mwh: 9528 },
    },
  ],
  by_hour_of_day: [{ hour: 0, summary }],
  by_issue_slot: [
    { slot_label: '09:30', available_at_cutoff: true, days: 31, summary },
    { slot_label: '11:30', available_at_cutoff: false, days: 30, summary },
  ],
  by_forecast_band: [
    { label: '0-5 GW', lower_mw: 0, upper_mw: 5000, summary },
    { label: '≥ 15 GW', lower_mw: 15000, upper_mw: null, summary },
  ],
  histogram: { bin_width_mw: 500, bins: [{ lower_mw: 0, upper_mw: 500, count: 10 }] },
  worst_over_forecast_hours: [
    {
      decision_date: '2026-01-11',
      delivery_date: '2026-01-12',
      target_time: '2026-01-12T01:00:00Z',
      forecast_mw: 20905,
      actual_mw: 14072,
      error_mw: 6833,
    },
  ],
  worst_under_forecast_hours: [],
}
