import { useQuery } from '@tanstack/react-query'
import { api } from './client'

export const queryKeys = {
  meta: ['meta'] as const,
  decisionDays: (cutoff: string | undefined) => ['decision-days', cutoff ?? 'default'] as const,
  forecast: (decisionDate: string, cutoff: string | undefined) =>
    ['forecast', decisionDate, cutoff ?? 'default'] as const,
  accuracy: (from: string | undefined, to: string | undefined, cutoff: string | undefined) =>
    ['accuracy', from ?? 'default', to ?? 'default', cutoff ?? 'default'] as const,
}

export function useMeta() {
  return useQuery({ queryKey: queryKeys.meta, queryFn: ({ signal }) => api.meta(signal) })
}

export function useDecisionDays(cutoff: string | undefined) {
  return useQuery({
    queryKey: queryKeys.decisionDays(cutoff),
    queryFn: ({ signal }) => api.decisionDays({ cutoff }, signal),
  })
}

export function useForecast(decisionDate: string | undefined, cutoff: string | undefined) {
  return useQuery({
    queryKey: queryKeys.forecast(decisionDate ?? '', cutoff),
    queryFn: ({ signal }) => api.forecast({ decisionDate: decisionDate ?? '', cutoff }, signal),
    enabled: Boolean(decisionDate),
  })
}

export function useAccuracy(
  from: string | undefined,
  to: string | undefined,
  cutoff: string | undefined,
) {
  return useQuery({
    queryKey: queryKeys.accuracy(from, to, cutoff),
    queryFn: ({ signal }) => api.accuracy({ from, to, cutoff }, signal),
  })
}
