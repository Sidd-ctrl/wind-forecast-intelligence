import { NavLink } from 'react-router-dom'
import { NAV_ITEMS } from '../../config/navigation'
import { BrandMark, Wordmark } from '../brand/BrandMark'
import { useDataset } from '../../hooks/useDataset'

export function NavRail() {
  const { dataMode, analysisDates } = useDataset()
  const windowLabel = analysisDates.length
    ? `${analysisDates[0]} → ${analysisDates[analysisDates.length - 1]}`
    : '2026-01-01 → 2026-01-31'

  return (
    <aside className="rail">
      <div className="rail__brand">
        <NavLink to="/" className="brand" aria-label="AERON home">
          <BrandMark />
          <Wordmark />
        </NavLink>
      </div>

      <nav className="rail__nav" aria-label="Primary">
        <p className="rail__section-label">Workspace</p>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) => `nav-item${isActive ? ' nav-item--active' : ''}`}
            >
              <Icon className="nav-item__icon" size={16} strokeWidth={1.6} aria-hidden="true" />
              <span>{item.label}</span>
              <span className="nav-item__index" aria-hidden="true">
                {item.index}
              </span>
            </NavLink>
          )
        })}
      </nav>

      <div className="rail__footer">
        <div className="divider-label">Dataset</div>
        <p className="rail__footnote">
          FUELHH · WINDFOR
          <br />
          {windowLabel}
          <br />
          {dataMode === 'sample' ? 'Sample snapshot' : 'Elexon BMRS retrieval'}
        </p>
      </div>
    </aside>
  )
}
