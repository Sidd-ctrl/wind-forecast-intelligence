export function ChartTooltip({ title, rows, foot }) {
  return (
    <div className="chart-tooltip">
      {title ? <div className="chart-tooltip__head">{title}</div> : null}
      {rows.map((row) => (
        <div className="chart-tooltip__row" key={row.label}>
          <span style={{ color: row.color || 'var(--muted)' }}>{row.label}</span>
          <span>{row.value}</span>
        </div>
      ))}
      {foot ? <div className="chart-tooltip__foot">{foot}</div> : null}
    </div>
  )
}

export function Legend({ items }) {
  return (
    <div className="chart-legend">
      {items.map((item) => (
        <span className="chart-legend__item" key={item.label}>
          <span
            className={`chart-legend__swatch${item.dashed ? ' chart-legend__swatch--dashed' : ''}`}
            style={{ borderTopColor: item.color }}
            aria-hidden="true"
          />
          {item.label}
        </span>
      ))}
    </div>
  )
}
