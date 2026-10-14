import { NavLink } from 'react-router-dom'
import { currentProject } from '../data'
import { useStore } from '../store'
import { Icon, type IconName } from './Icon'
import { StatusDot } from './StatusIndicator'
import { Kbd, modKey, Tooltip } from './Tooltip'

export const navItems: { to: string; label: string; icon: IconName; end?: boolean }[] = [
  { to: '/app', label: 'Overview', icon: 'overview', end: true },
  { to: '/app/workspace', label: 'Workspace', icon: 'workspace' },
  { to: '/app/intelligence', label: 'Intelligence', icon: 'intelligence' },
  { to: '/app/activity', label: 'Activity', icon: 'activity' },
  { to: '/app/data', label: 'Data', icon: 'data' },
  { to: '/app/settings', label: 'Settings', icon: 'settings' },
]

export function Sidebar() {
  const { tasks, setPaletteOpen } = useStore()
  const running = tasks.filter((t) => t.status === 'running').length
  return (
    <nav className="sidebar" aria-label="Primary">
      <div className="side-section">
        <span className="label side-label">Command</span>
        {navItems.map((n) => (
          <Tooltip key={n.to} label={n.label} side="right">
            <NavLink to={n.to} end={n.end} className="nav-item">
              <Icon name={n.icon} size={17} />
              <span className="nav-text">{n.label}</span>
              {n.label === 'Workspace' && running > 0 && <span className="nav-badge mono">{running}</span>}
            </NavLink>
          </Tooltip>
        ))}
      </div>

      <div className="side-section side-project">
        <span className="label side-label">Active project</span>
        <div className="project-card">
          <span className="mono xs muted">{currentProject.code}</span>
          <strong>{currentProject.name}</strong>
          <StatusDot state="processing" label={`${running} running`} />
        </div>
      </div>

      <div className="side-foot">
        <button className="side-cmd" onClick={() => setPaletteOpen(true)}>
          <Icon name="command" size={14} />
          <span className="nav-text">Command</span>
          <span className="nav-text"><Kbd>{modKey}</Kbd><Kbd>K</Kbd></span>
        </button>
        <div className="side-health mono xs">
          <StatusDot state="operational" />
          <span className="nav-text">All systems nominal</span>
        </div>
      </div>
    </nav>
  )
}

// Mobile: a focused bottom bar with the AI front and centre.
export function BottomNav() {
  return (
    <nav className="bottom-nav" aria-label="Primary">
      <NavLink to="/app" end className="bn-item"><Icon name="overview" size={19} /><span>Focus</span></NavLink>
      <NavLink to="/app/activity" className="bn-item"><Icon name="activity" size={19} /><span>Activity</span></NavLink>
      <NavLink to="/app/workspace" className="bn-item bn-ask" aria-label="Ask Nexa"><span className="orb" /></NavLink>
      <NavLink to="/app/intelligence" className="bn-item"><Icon name="intelligence" size={19} /><span>Insights</span></NavLink>
      <NavLink to="/app/data" className="bn-item"><Icon name="data" size={19} /><span>Data</span></NavLink>
    </nav>
  )
}
