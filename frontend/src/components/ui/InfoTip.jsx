import { useId, useState } from 'react'

export function InfoTip({ text, align = 'center' }) {
  const [open, setOpen] = useState(false)
  const id = useId()

  return (
    <span
      style={{ position: 'relative', display: 'inline-flex' }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        className="info-tip"
        aria-describedby={open ? id : undefined}
        aria-label="Metric definition"
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={(event) => {
          event.preventDefault()
          setOpen((value) => !value)
        }}
      >
        i
      </button>
      {open ? (
        <span role="tooltip" id={id} className={`info-tip__bubble${align === 'right' ? ' info-tip__bubble--right' : ''}`}>
          {text}
        </span>
      ) : null}
    </span>
  )
}
