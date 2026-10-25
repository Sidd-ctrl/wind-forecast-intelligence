import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'

export function NotFoundPage() {
  return (
    <div className="state-block" style={{ marginTop: 40 }}>
      <Compass size={22} style={{ color: 'var(--muted-dim)' }} />
      <p className="state-block__title">Route not found</p>
      <p className="state-block__text">
        This address is not part of the AERON workspace. Use the navigation rail to return to the trading overview.
      </p>
      <Link className="btn btn--primary" to="/">
        Back to overview
      </Link>
    </div>
  )
}
