/** Typed client. Response types are generated from the backend OpenAPI document. */
import type { components } from './schema'

type Schemas = components['schemas']

export type Meta = Schemas['MetaDTO']
export type DecisionDays = Schemas['DecisionDaysDTO']
export type DecisionDay = Schemas['DecisionDayDTO']
export type DecisionView = Schemas['DecisionViewDTO']
export type Issue = Schemas['IssueDTO']
export type Point = Schemas['PointDTO']
export type HourlyActual = Schemas['HourlyActualDTO']
export type ErrorPair = Schemas['ErrorPairDTO']
export type ErrorSummary = Schemas['ErrorSummaryDTO']
export type Energy = Schemas['EnergyDTO']
export type AccuracyReport = Schemas['AccuracyReportDTO']
export type DailyAccuracy = Schemas['DailyAccuracyDTO']
export type HourOfDay = Schemas['HourOfDayDTO']
export type IssueSlot = Schemas['IssueSlotDTO']
export type WorstHour = Schemas['WorstHourDTO']
export type Guidance = Schemas['ProcurementGuidanceDTO']
export type CoverageOption = Schemas['CoverageOptionDTO']
export type Baseline = Schemas['BaselineDTO']
export type Calibration = Schemas['CalibrationDTO']
export type BandPoint = Schemas['BandPointDTO']
export type ForecastBand = Schemas['ForecastBandDTO']
export type BandBacktest = Schemas['BandBacktestDTO']

export interface ProblemDetails {
  type?: string
  title: string
  status: number
  detail?: string
  instance?: string
  errors?: Record<string, string>
  [key: string]: unknown
}

export class ApiError extends Error {
  readonly status: number
  readonly problem: ProblemDetails | undefined

  constructor(status: number, message: string, problem?: ProblemDetails) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.problem = problem
  }
}

const BASE = '/api/v1'

function buildUrl(path: string, params: Record<string, string | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, value)
  }
  const query = search.toString()
  return query ? `${BASE}${path}?${query}` : `${BASE}${path}`
}

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const init: RequestInit = { headers: { Accept: 'application/json' } }
  if (signal) init.signal = signal
  const response = await fetch(url, init)
  if (response.ok) {
    return (await response.json()) as T
  }
  let problem: ProblemDetails | undefined
  try {
    problem = (await response.json()) as ProblemDetails
  } catch {
    problem = undefined
  }
  const message = problem?.detail ?? problem?.title ?? `Request failed with HTTP ${response.status}`
  throw new ApiError(response.status, message, problem)
}

export interface CutoffParam {
  cutoff?: string | undefined
}

export const api = {
  meta: (signal?: AbortSignal) => getJson<Meta>(`${BASE}/meta`, signal),

  decisionDays: ({ cutoff }: CutoffParam, signal?: AbortSignal) =>
    getJson<DecisionDays>(buildUrl('/decision-days', { cutoff }), signal),

  forecast: (
    { decisionDate, cutoff }: CutoffParam & { decisionDate: string },
    signal?: AbortSignal,
  ) =>
    getJson<DecisionView>(buildUrl('/forecast', { decision_date: decisionDate, cutoff }), signal),

  accuracy: (
    { from, to, cutoff }: CutoffParam & { from?: string | undefined; to?: string | undefined },
    signal?: AbortSignal,
  ) => getJson<AccuracyReport>(buildUrl('/accuracy', { from, to, cutoff }), signal),

  accuracyCsvUrl: ({
    from,
    to,
    cutoff,
  }: CutoffParam & { from?: string | undefined; to?: string | undefined }) =>
    buildUrl('/accuracy/export.csv', { from, to, cutoff }),
}
