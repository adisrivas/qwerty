import type { ReactNode } from 'react'

interface StatTileProps {
  label: string
  value: string
  unit?: string | undefined
  hint?: ReactNode
  tone?: 'over' | 'under' | 'neutral' | undefined
}

export function StatTile({ label, value, unit, hint, tone = 'neutral' }: StatTileProps) {
  const toneClass = tone === 'over' ? 'pos' : tone === 'under' ? 'neg' : undefined
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className={`stat-value${toneClass ? ` ${toneClass}` : ''}`}>
        {value}
        {unit ? <small>{unit}</small> : null}
      </span>
      {hint ? <span className="stat-hint">{hint}</span> : null}
    </div>
  )
}
