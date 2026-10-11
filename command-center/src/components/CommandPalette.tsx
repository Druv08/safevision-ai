import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { records } from '../data'
import { useStore } from '../store'
import { Icon, type IconName } from './Icon'
import { Kbd, modKey } from './Tooltip'

interface Command {
  id: string
  group: string
  label: string
  hint?: string
  icon: IconName
  keys?: string
  run: () => void
}

export function CommandPalette() {
  const s = useStore()
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const [active, setActive] = useState(0)
  const ref = useRef<HTMLDialogElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (s.paletteOpen && !d.open) { setQ(''); setActive(0); d.showModal() }
    if (!s.paletteOpen && d.open) d.close()
  }, [s.paletteOpen])

  const close = () => s.setPaletteOpen(false)
  const go = (path: string) => () => nav(path)

  const commands: Command[] = useMemo(() => [
    { id: 'ask', group: 'Intelligence', label: 'Ask Nexa', hint: 'Open the AI workspace', icon: 'spark', keys: 'A', run: go('/app/workspace') },
    { id: 'analyze', group: 'Intelligence', label: 'Analyze current view', hint: 'Summarise what changed', icon: 'intelligence', run: () => { s.setPendingPrompt('Summarize what changed in the last 24 hours'); nav('/app/workspace') } },
    { id: 'run', group: 'Run', label: 'Run analysis pipeline', hint: 'Queues a new run', icon: 'play', keys: 'R', run: () => { s.addTask('Ad-hoc analysis run', 'analyze'); s.toast({ kind: 'info', title: 'Analysis queued', body: 'Run it from the task queue on Overview' }) } },
    { id: 'run-all', group: 'Run', label: 'Run all queued tasks', icon: 'play', run: () => { const q = s.tasks.filter((t) => t.status === 'queued' || t.status === 'failed'); q.forEach((t) => s.runTask(t.id)); s.toast({ kind: 'success', title: `${q.length} tasks started` }) } },
    { id: 'create', group: 'Create', label: 'New task', hint: 'Open the create dialog', icon: 'plus', keys: 'N', run: () => s.setCreateOpen(true) },
    { id: 'nav-overview', group: 'Navigate', label: 'Overview', icon: 'overview', run: go('/app') },
    { id: 'nav-workspace', group: 'Navigate', label: 'Workspace', icon: 'workspace', run: go('/app/workspace') },
    { id: 'nav-intel', group: 'Navigate', label: 'Intelligence', icon: 'intelligence', run: go('/app/intelligence') },
    { id: 'nav-activity', group: 'Navigate', label: 'Activity', icon: 'activity', run: go('/app/activity') },
    { id: 'nav-data', group: 'Navigate', label: 'Data sources', icon: 'data', run: go('/app/data') },
    { id: 'panel', group: 'View', label: s.panelOpen ? 'Hide intelligence panel' : 'Show intelligence panel', icon: 'panel', run: () => s.setPanelOpen(!s.panelOpen) },
    { id: 'settings', group: 'Settings', label: 'Open settings', icon: 'settings', keys: ',', run: go('/app/settings') },
    { id: 'landing', group: 'Settings', label: 'Back to landing page', icon: 'logout', run: go('/') },
  ], [s, nav])

  // Global shortcuts: Cmd/Ctrl+K toggles the palette; single keys (shown as hints) run commands
  // when focus isn't in a text field.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        s.setPaletteOpen(!s.paletteOpen)
        return
      }
      const el = e.target as HTMLElement
      if (e.metaKey || e.ctrlKey || e.altKey || s.paletteOpen || el.closest('input, textarea, select, [contenteditable], dialog')) return
      const c = commands.find((c) => c.keys === e.key.toUpperCase())
      if (c) { e.preventDefault(); c.run() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [s, commands])

  const results = useMemo(() => {
    const term = q.trim().toLowerCase()
    if (!term) return commands
    const matched = commands.filter((c) => `${c.group} ${c.label} ${c.hint ?? ''}`.toLowerCase().includes(term))
    const recs = records.filter((r) => r.name.toLowerCase().includes(term)).slice(0, 3).map<Command>((r) => ({
      id: `rec-${r.id}`, group: 'Data', label: r.name, hint: `${r.type} · ${r.id}`, icon: 'data', run: go('/app/data'),
    }))
    return [
      { id: 'ask-q', group: 'Ask', label: `Ask Nexa: "${q.trim()}"`, icon: 'spark', run: () => { s.setPendingPrompt(q.trim()); nav('/app/workspace') } } as Command,
      ...matched,
      ...recs,
    ]
  }, [q, commands])

  useEffect(() => setActive(0), [q])
  useEffect(() => { listRef.current?.querySelector('[data-active="true"]')?.scrollIntoView({ block: 'nearest' }) }, [active])

  const exec = (c: Command) => { close(); c.run() }
  let lastGroup = ''

  return (
    <dialog ref={ref} className="palette" onClose={close} onClick={(e) => e.target === ref.current && close()}>
      {s.paletteOpen && (
        <div className="palette-inner">
          <div className="palette-search">
            <Icon name="search" size={18} />
            <input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Type a command, search, or ask a question..."
              aria-label="Command"
              onKeyDown={(e) => {
                if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => (a + 1) % results.length) }
                if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => (a - 1 + results.length) % results.length) }
                if (e.key === 'Enter' && results[active]) { e.preventDefault(); exec(results[active]) }
              }}
            />
            <Kbd>Esc</Kbd>
          </div>
          <div className="palette-list" ref={listRef} role="listbox">
            {results.map((c, i) => {
              const header = c.group !== lastGroup ? (lastGroup = c.group) : null
              return (
                <div key={c.id}>
                  {header && <div className="palette-group">{header}</div>}
                  <button
                    role="option"
                    aria-selected={i === active}
                    data-active={i === active}
                    className="palette-item"
                    onMouseMove={() => setActive(i)}
                    onClick={() => exec(c)}
                  >
                    <span className="palette-icon"><Icon name={c.icon} size={15} /></span>
                    <span className="palette-label">{c.label}{c.hint && <span className="muted"> — {c.hint}</span>}</span>
                    {c.keys && <span className="palette-keys">{c.keys.split(' ').map((k) => <Kbd key={k}>{k}</Kbd>)}</span>}
                    <Icon name="arrowRight" size={14} className="palette-enter" />
                  </button>
                </div>
              )
            })}
          </div>
          <footer className="palette-foot mono xs">
            <span><Kbd>↑</Kbd><Kbd>↓</Kbd> navigate</span>
            <span><Kbd>↵</Kbd> run</span>
            <span className="spacer" />
            <span><Kbd>{modKey}</Kbd><Kbd>K</Kbd> toggle</span>
          </footer>
        </div>
      )}
    </dialog>
  )
}
