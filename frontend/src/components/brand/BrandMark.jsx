export function BrandMark({ size = 30 }) {
  return (
    <svg
      className="brand__mark"
      width={size}
      height={size}
      viewBox="0 0 32 32"
      role="img"
      aria-label="AERON mark"
      style={{ width: size, height: size }}
    >
      <rect x="0.5" y="0.5" width="31" height="31" stroke="rgba(233,240,234,0.16)" fill="none" />
      <path d="M6.5 24.5 L16 6.8 L25.5 24.5" fill="none" stroke="var(--lime)" strokeWidth="2.1" strokeLinejoin="round" />
      <path d="M10.6 20.2 H21.4" stroke="var(--lime)" strokeWidth="1.5" />
      <circle cx="16" cy="6.8" r="1.9" fill="var(--paper)" />
      <path d="M4 28.4 H28" stroke="rgba(233,240,234,0.3)" strokeWidth="1" />
    </svg>
  )
}

export function Wordmark() {
  return (
    <div>
      <div className="brand__wordmark">AERON</div>
      <div className="brand__sub">Wind Forecast Intelligence</div>
    </div>
  )
}
