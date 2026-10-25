import { InfoTip } from './InfoTip'

export function ReadoutStrip({ children, label = 'Key accuracy indicators' }) {
  return (
    <div className="readout-strip" role="group" aria-label={label}>
      {children}
    </div>
  )
}

export function Readout({ label, value, unit, foot, tone = 'neutral', tip }) {
  return (
    <div className={`readout${tone !== 'neutral' ? ` readout--${tone}` : ''}`}>
      <span className="readout__rule" aria-hidden="true" />
      <div className="readout__top">
        <span className="readout__label">{label}</span>
        {tip ? <InfoTip text={tip} align="right" /> : null}
      </div>
      <div className="readout__value">
        {value}
        {unit ? <span className="readout__unit">{unit}</span> : null}
      </div>
      {foot ? <div className="readout__foot">{foot}</div> : null}
    </div>
  )
}
