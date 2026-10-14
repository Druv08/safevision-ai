import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ago, product, workspaces } from '../data'
import { useStore } from '../store'
import { Icon, Logo } from './Icon'
import { StatusDot } from './StatusIndicator'
import { Kbd, modKey, Tooltip } from './Tooltip'

// Click-outside / Esc popover. Small enough not to need a library.
function Popover({ trigger, children, align = 'right', label }: { trigger: (open: boolean) => ReactNode; children: (close: () => void) => ReactNode; align?: 'left' | 'right'; label: string }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey) }
  }, [open])
  return (
    <div className="pop" ref={ref}>
      <button className="pop-trigger" aria-expanded={open} aria-haspopup="menu" aria-label={label} onClick={() => setOpen((o) => !o)}>{trigger(open)}</button>
      {open && <div className={`pop-menu pop-${align}`} role="menu">{children(() => setOpen(false))}</div>}
    </div>
  )
}

export function TopBar() {
  const s = useStore()
  const nav = useNavigate()
  const ws = workspaces.find((w) => w.id === s.workspaceId)!
  const unread = s.notifications.filter((n) => !n.read).length

  return (
    <header className="topbar">
      <Link to="/" className="brand" aria-label={`${product.name} home`}>
        <Logo />
        <span className="brand-name">{product.name}</span>
      </Link>

      <span className="topbar-sep hide-mobile" />

      <Popover
        label="Switch workspace"
        align="left"
        trigger={(open) => (
          <span className="ws-trigger">
            <span className="ws-avatar">{ws.name[0]}</span>
            <span className="ws-name">{ws.name}</span>
            <span className="env mono hide-mobile">{ws.env}</span>
            <Icon name="chevronDown" size={14} className={open ? 'rot180' : ''} />
          </span>
        )}
      >
        {(close) => (
          <>
            <div className="pop-label label">Workspaces</div>
            {workspaces.map((w) => (
              <button key={w.id} role="menuitem" className="pop-item" onClick={() => { s.setWorkspaceId(w.id); close(); s.toast({ kind: 'info', title: `Switched to ${w.name}` }) }}>
                <span className="ws-avatar">{w.name[0]}</span>{w.name}<span className="env mono">{w.env}</span>
                {w.id === s.workspaceId && <Icon name="check" size={14} className="accent" />}
              </button>
            ))}
          </>
        )}
      </Popover>

      <button className="search-trigger" onClick={() => s.setPaletteOpen(true)}>
        <Icon name="search" size={15} />
        <span>Search or run a command...</span>
        <span className="search-keys"><Kbd>{modKey}</Kbd><Kbd>K</Kbd></span>
      </button>

      <div className="topbar-right">
        <Tooltip label={s.aiBusy ? 'Model is reasoning' : 'Model v4 online · 142ms p95'}>
          <span className={`ai-chip ${s.aiBusy ? 'busy' : ''}`}>
            <StatusDot state={s.aiBusy ? 'processing' : 'operational'} />
            <span className="mono xs">AI</span>
            <span className="hide-tablet">{s.aiBusy ? 'Processing' : 'Active'}</span>
          </span>
        </Tooltip>

        <button className="icon-btn show-mobile" onClick={() => s.setPaletteOpen(true)} aria-label="Search"><Icon name="search" size={17} /></button>

        <Popover
          label="Notifications"
          trigger={() => (
            <span className="icon-btn">
              <Icon name="bell" size={17} />
              {unread > 0 && <span className="badge">{unread}</span>}
            </span>
          )}
        >
          {(close) => (
            <div className="notif">
              <div className="notif-head">
                <strong>Notifications</strong>
                <button className="btn ghost sm" onClick={s.markAllRead} disabled={!unread}>Mark all read</button>
              </div>
              {s.notifications.map((n) => (
                <button key={n.id} className={`notif-item ${n.read ? '' : 'unread'}`} onClick={() => { close(); nav('/app/activity') }}>
                  <i />
                  <div><strong>{n.title}</strong><span>{n.body}</span></div>
                  <time className="mono xs muted">{ago(n.at)}</time>
                </button>
              ))}
            </div>
          )}
        </Popover>

        <Tooltip label={s.panelOpen ? 'Hide context panel' : 'Show context panel'}>
          <button className={`icon-btn hide-mobile ${s.panelOpen ? 'on' : ''}`} onClick={() => s.setPanelOpen(!s.panelOpen)} aria-label="Toggle intelligence panel" aria-pressed={s.panelOpen}>
            <Icon name="panel" size={17} />
          </button>
        </Tooltip>

        <Popover
          label="User menu"
          trigger={() => <span className="avatar">AK</span>}
        >
          {(close) => (
            <>
              <div className="pop-user">
                <span className="avatar lg">AK</span>
                <div><strong>Alex Kim</strong><span className="muted xs">alex@nexa.dev · Admin</span></div>
              </div>
              <button className="pop-item" onClick={() => { close(); nav('/app/settings') }}><Icon name="user" size={15} />Profile & settings</button>
              <button className="pop-item" onClick={() => { close(); s.setPaletteOpen(true) }}><Icon name="command" size={15} />Command palette</button>
              <div className="pop-sep" />
              <button className="pop-item" onClick={() => nav('/')}><Icon name="logout" size={15} />Sign out</button>
            </>
          )}
        </Popover>
      </div>
    </header>
  )
}
