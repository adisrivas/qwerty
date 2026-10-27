export interface LegendItem {
  label: string
  color: string
  shape?: 'line' | 'box'
  dashed?: boolean
}

export function Legend({ items }: { items: LegendItem[] }) {
  return (
    <div className="legend" aria-label="Legend">
      {items.map((item) => (
        <span className="legend-item" key={item.label}>
          <span
            className={`legend-swatch${item.shape === 'box' ? ' box' : ''}`}
            style={
              item.dashed
                ? {
                    background: 'none',
                    borderTop: `2px dashed ${item.color}`,
                    height: 0,
                  }
                : { background: item.color }
            }
            aria-hidden="true"
          />
          {item.label}
        </span>
      ))}
    </div>
  )
}
