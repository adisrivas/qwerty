import { ApiError } from '../api/client'

export function LoadingState({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="card" role="status" aria-live="polite">
      <span className="visually-hidden">{label}</span>
      <div className="skeleton" aria-hidden="true" />
    </div>
  )
}

export function ErrorState({ error }: { error: unknown }) {
  const message =
    error instanceof ApiError
      ? error.message
      : error instanceof Error
        ? error.message
        : 'Something went wrong.'
  const status = error instanceof ApiError ? `HTTP ${error.status}` : undefined
  return (
    <div className="card state" role="alert">
      <strong>Could not load this view.</strong>
      <p>{message}</p>
      {status ? <code>{status}</code> : null}
    </div>
  )
}
