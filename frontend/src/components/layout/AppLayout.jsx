import { Outlet } from 'react-router-dom'
import { NavRail } from './NavRail'
import { TopBar } from './TopBar'

export function AppLayout() {
  return (
    <div className="shell">
      <NavRail />
      <div className="main-column">
        <TopBar />
        <main className="page page-enter">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
