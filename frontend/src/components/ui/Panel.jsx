export function Panel({ children, className = '', as: Element = 'section' }) {
  return <Element className={`panel ${className}`.trim()}>{children}</Element>
}

export function PanelHead({ title, hint, children, id }) {
  return (
    <header className="panel__head">
      <h2 className="panel__title" id={id}>
        {title}
      </h2>
      {hint ? <span className="panel__hint">{hint}</span> : null}
      <span className="panel__head-spacer" />
      {children}
    </header>
  )
}

export function PanelBody({ children, flush = false, className = '' }) {
  return <div className={`panel__body${flush ? ' panel__body--flush' : ''} ${className}`.trim()}>{children}</div>
}
