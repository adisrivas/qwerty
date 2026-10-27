import { useId, useState } from 'react'
import { CUTOFF_PRESETS } from '../lib/cutoffs'
import { TIME_RE } from '../lib/format'

interface CutoffFieldProps {
  value: string
  onChange: (cutoff: string) => void
}

export function CutoffField({ value, onChange }: CutoffFieldProps) {
  const id = useId()
  const isPreset = CUTOFF_PRESETS.some((p) => p.value === value)
  const [custom, setCustom] = useState(!isPreset)
  const selectValue = custom ? 'custom' : value

  return (
    <>
      <label className="field" htmlFor={`${id}-select`}>
        Cutoff (UK time)
        <select
          id={`${id}-select`}
          value={selectValue}
          onChange={(e) => {
            if (e.target.value === 'custom') {
              setCustom(true)
            } else {
              setCustom(false)
              onChange(e.target.value)
            }
          }}
        >
          {CUTOFF_PRESETS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
          <option value="custom">Custom time</option>
        </select>
      </label>
      {custom ? (
        <label className="field" htmlFor={`${id}-time`}>
          Custom cutoff
          <input
            id={`${id}-time`}
            type="time"
            value={value}
            step={60}
            onChange={(e) => {
              if (TIME_RE.test(e.target.value)) onChange(e.target.value)
            }}
          />
        </label>
      ) : null}
    </>
  )
}
