import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { CommandPalette } from '../components/CommandPalette'
import { IntelligencePanel } from '../components/IntelligencePanel'
import { Modal } from '../components/Modal'
import { BottomNav, Sidebar } from '../components/Sidebar'
import { Toaster } from '../components/Toast'
import { TopBar } from '../components/TopBar'
import { useStore } from '../store'

export function AppShell() {
  const { panelOpen, setPanelOpen } = useStore()
  const { pathname } = useLocation()
  // On narrow screens the panel is an overlay; close it when navigating.
  useEffect(() => { if (window.innerWidth < 1280) setPanelOpen(false) }, [pathname, setPanelOpen])

  return (
    <div className={`shell ${panelOpen ? 'panel-open' : ''}`}>
      <TopBar />
      <Sidebar />
      <main className="main" key={pathname}>
        <Outlet />
      </main>
      <IntelligencePanel />
      <div className="scrim" onClick={() => setPanelOpen(false)} />
      <BottomNav />
      <CommandPalette />
      <CreateTaskModal />
      <Toaster />
    </div>
  )
}

const types = ['analyze', 'ingest', 'model', 'report', 'quality'] as const
const priorities = ['Low', 'Normal', 'High'] as const

function CreateTaskModal() {
  const { createOpen, setCreateOpen, addTask, toast } = useStore()
  const [title, setTitle] = useState('')
  const [type, setType] = useState<string>('analyze')
  const [priority, setPriority] = useState<string>('Normal')
  const [runNow, setRunNow] = useState(true)
  const [touched, setTouched] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const error = title.trim().length < 3 ? 'Give the task a name of at least 3 characters.' : ''

  const close = () => { setCreateOpen(false); setTitle(''); setTouched(false) }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    setTouched(true)
    if (error) return inputRef.current?.focus()
    addTask(title.trim(), type, runNow)
    toast({ kind: 'success', title: 'Task created', body: `${title.trim()} · ${priority} priority` })
    close()
  }
  return (
    <Modal
      open={createOpen}
      onClose={close}
      eyebrow="Create"
      title="New task"
      footer={
        <>
          <button className="btn ghost" type="button" onClick={close}>Cancel</button>
          <button className="btn btn-accent" type="submit" form="create-task">Create task</button>
        </>
      }
    >
      <form id="create-task" className="form" onSubmit={submit} noValidate>
        <label className="field">
          <span>Task name</span>
          <input ref={inputRef} autoFocus value={title} onChange={(e) => setTitle(e.target.value)} onBlur={() => setTouched(true)} placeholder="e.g. Cluster anomalies in Stream B" aria-invalid={touched && !!error} />
          {touched && error && <em className="field-error">{error}</em>}
        </label>
        <div className="form-row">
          <label className="field">
            <span>Type</span>
            <select value={type} onChange={(e) => setType(e.target.value)}>
              {types.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <div className="field">
            <span>Priority</span>
            <div className="seg">
              {priorities.map((p) => <button type="button" key={p} className={p === priority ? 'on' : ''} onClick={() => setPriority(p)}>{p}</button>)}
            </div>
          </div>
        </div>
        <label className="toggle-row">
          <input type="checkbox" className="switch" checked={runNow} onChange={(e) => setRunNow(e.target.checked)} />
          <div><strong>Run immediately</strong><span className="muted">Start processing as soon as the task is created.</span></div>
        </label>
      </form>
    </Modal>
  )
}
