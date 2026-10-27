import type { ReactNode } from 'react'

interface CalloutProps {
  kind?: 'info' | 'warn' | 'bad'
  title?: string | undefined
  children: ReactNode
}

export function Callout({ kind = 'info', title, children }: CalloutProps) {
  const cls =
    kind === 'warn' ? 'callout callout-warn' : kind === 'bad' ? 'callout callout-bad' : 'callout'
  return (
    <div className={cls} role={kind === 'info' ? undefined : 'alert'}>
      {title ? <strong>{title}</strong> : null}
      {children}
    </div>
  )
}
