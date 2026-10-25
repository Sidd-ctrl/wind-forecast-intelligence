import { useLocation } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import { findNavItem } from '../../config/navigation'
import { useDataset } from '../../hooks/useDataset'

export function TopBar() {
  const location = useLocation()
  const page = findNavItem(location.pathname)
  const { dataMode, health, healthStatus, healthError, isRefreshing, refresh, retrievalLabel, cacheStatus } = useDataset()

  const apiOnline = healthStatus === 'ready'
  const ledClass = apiOnline ? 'status-led status-led--pulse' : 'status-led status-led--off'
  const apiLabel = apiOnline ? 'API online' : healthStatus === 'loading' ? 'API checking' : 'API offline'

  return (
    <header className="topbar">
      <div className="topbar__trail">
        <span className="topbar__eyebrow">AERON / {page.eyebrow}</span>
        <span className="topbar__page">{page.label}</span>
      </div>

      <div className="topbar__spacer" />

      <div className="topbar__status">
        <span className={`status-chip ${dataMode === 'sample' ? 'status-chip--sample' : 'status-chip--live'}`}>
          <span className={dataMode === 'sample' ? 'status-led status-led--amber' : 'status-led'} aria-hidden="true" />
          {dataMode === 'sample' ? 'Sample data' : dataMode === 'live' ? 'Live Elexon data' : 'Mode unknown'}
        </span>

        <span className="status-chip" title={healthError ? healthError.message : 'Backend health endpoint reachable'}>
          <span className={ledClass} aria-hidden="true" />
          {apiLabel}
        </span>

        {cacheStatus ? <span className="status-chip">Cache · {cacheStatus}</span> : null}

        {retrievalLabel ? (
          <span className="status-chip" title="Time the historical datasets were retrieved">
            Retrieved · {retrievalLabel}
          </span>
        ) : null}

        <button
          type="button"
          className="btn btn--primary"
          onClick={refresh}
          disabled={isRefreshing}
          aria-label="Refresh historical datasets from Elexon"
        >
          <RefreshCw size={13} className={isRefreshing ? 'spin' : ''} aria-hidden="true" />
          {isRefreshing ? 'Refreshing' : 'Refresh'}
        </button>
      </div>
    </header>
  )
}
