import { NavLink, Outlet } from 'react-router-dom'
import { useMeta } from '../api/queries'
import { ukDate } from '../lib/format'

export function Layout() {
  const meta = useMeta()
  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/decision" className="brand">
            Day-ahead Wind Forecast
          </NavLink>
          <nav className="nav" aria-label="Main">
            <NavLink to="/decision">Decision</NavLink>
            <NavLink to="/accuracy">Accuracy</NavLink>
            <NavLink to="/about">Method and data</NavLink>
          </nav>
        </div>
      </header>
      <main className="main">
        <Outlet />
      </main>
      <footer className="footer">
        <div className="footer-inner">
          <span>Data: Elexon Insights (WINDFOR, FUELHH). Times are UK local.</span>
          {meta.data?.snapshot ? (
            <span>Data snapshot {ukDate(meta.data.snapshot.created_at.slice(0, 10))}</span>
          ) : null}
        </div>
      </footer>
    </div>
  )
}
