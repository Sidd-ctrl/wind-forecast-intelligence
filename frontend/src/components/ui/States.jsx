import { AlertOctagon, Inbox, RotateCcw } from 'lucide-react'

export function ReadoutSkeleton({ count = 6 }) {
  return (
    <div className="readout-strip" aria-hidden="true">
      {Array.from({ length: count }).map((_, index) => (
        <div className="readout" key={index}>
          <div className="skeleton skeleton-text" style={{ width: '52%' }} />
          <div className="skeleton skeleton-value" />
          <div className="skeleton skeleton-text" style={{ width: '74%', marginTop: 12, height: 8 }} />
        </div>
      ))}
    </div>
  )
}

export function ChartSkeleton({ height = 320 }) {
  return (
    <div className="stack-sm" aria-hidden="true">
      <div className="skeleton" style={{ height, width: '100%' }} />
      <div className="skeleton skeleton-text" style={{ width: '38%', height: 8 }} />
    </div>
  )
}

export function TableSkeleton({ rows = 8 }) {
  return (
    <div className="stack-sm" aria-hidden="true" style={{ padding: 18 }}>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton skeleton-text" style={{ width: `${100 - (index % 4) * 9}%` }} />
      ))}
    </div>
  )
}

export function EmptyState({ title = 'No records', text, action }) {
  return (
    <div className="state-block">
      <Inbox size={20} style={{ color: 'var(--muted-dim)' }} />
      <p className="state-block__title">{title}</p>
      {text ? <p className="state-block__text">{text}</p> : null}
      {action}
    </div>
  )
}

export function ErrorState({ error, onRetry, title = 'Request failed' }) {
  return (
    <div className="state-block state-block--error" role="alert">
      <AlertOctagon size={20} style={{ color: 'var(--crit)' }} />
      <p className="state-block__title">{title}</p>
      <p className="state-block__text">{error?.message || 'The backend could not complete this request.'}</p>
      {error?.code ? <span className="tag">code · {error.code}</span> : null}
      {onRetry ? (
        <button type="button" className="btn" onClick={onRetry}>
          <RotateCcw size={13} />
          Retry request
        </button>
      ) : null}
    </div>
  )
}
