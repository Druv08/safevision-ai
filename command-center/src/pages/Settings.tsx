import { useState, type FormEvent } from 'react'
import { DataCard } from '../components/DataCard'
import { Modal } from '../components/Modal'
import { useStore } from '../store'

export function Settings() {
  const { toast } = useStore()
  const [profile, setProfile] = useState({ name: 'Alex Kim', email: 'alex@nexa.dev', role: 'Admin' })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [ai, setAi] = useState({ model: 'Nexa v4 (balanced)', creativity: 35, cite: true, autorun: false })
  const [notify, setNotify] = useState({ insights: true, failures: true, digest: false })
  const [resetOpen, setResetOpen] = useState(false)
  const [confirm, setConfirm] = useState('')

  const save = (e: FormEvent) => {
    e.preventDefault()
    const errs: Record<string, string> = {}
    if (!profile.name.trim()) errs.name = 'Name is required.'
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(profile.email)) errs.email = 'Enter a valid email address.'
    setErrors(errs)
    if (Object.keys(errs).length) return toast({ kind: 'error', title: 'Fix the highlighted fields' })
    setSaving(true)
    setTimeout(() => { setSaving(false); toast({ kind: 'success', title: 'Profile saved' }) }, 700)
  }

  return (
    <div className="page page-narrow">
      <section className="page-head">
        <div>
          <div className="eyebrow">Settings</div>
          <h1>Preferences</h1>
        </div>
      </section>

      <DataCard eyebrow="Account" title="Profile">
        <form className="form" onSubmit={save} noValidate>
          <div className="form-row">
            <label className="field">
              <span>Full name</span>
              <input value={profile.name} onChange={(e) => setProfile({ ...profile, name: e.target.value })} aria-invalid={!!errors.name} />
              {errors.name && <em className="field-error">{errors.name}</em>}
            </label>
            <label className="field">
              <span>Email</span>
              <input type="email" value={profile.email} onChange={(e) => setProfile({ ...profile, email: e.target.value })} aria-invalid={!!errors.email} />
              {errors.email && <em className="field-error">{errors.email}</em>}
            </label>
          </div>
          <label className="field">
            <span>Role</span>
            <select value={profile.role} onChange={(e) => setProfile({ ...profile, role: e.target.value })}>
              {['Admin', 'Analyst', 'Viewer'].map((r) => <option key={r}>{r}</option>)}
            </select>
          </label>
          <div className="row end">
            <button className="btn btn-accent" disabled={saving}>{saving ? <><span className="spinner" />Saving</> : 'Save changes'}</button>
          </div>
        </form>
      </DataCard>

      <DataCard eyebrow="Model" title="Intelligence">
        <div className="form">
          <label className="field">
            <span>Reasoning model</span>
            <select value={ai.model} onChange={(e) => { setAi({ ...ai, model: e.target.value }); toast({ kind: 'info', title: 'Model updated', body: e.target.value }) }}>
              {['Nexa v4 (balanced)', 'Nexa v4 (fast)', 'Nexa v4 (deep reasoning)'].map((m) => <option key={m}>{m}</option>)}
            </select>
          </label>
          <label className="field">
            <span className="row between">Creativity <b className="mono xs accent">{ai.creativity}</b></span>
            <input type="range" min={0} max={100} value={ai.creativity} onChange={(e) => setAi({ ...ai, creativity: +e.target.value })} style={{ ['--v' as string]: `${ai.creativity}%` }} />
          </label>
          <Toggle label="Always cite sources" sub="Every answer links to the data it used." checked={ai.cite} onChange={(v) => setAi({ ...ai, cite: v })} />
          <Toggle label="Auto-run recommended actions" sub="Low-risk actions run without confirmation." checked={ai.autorun} onChange={(v) => setAi({ ...ai, autorun: v })} />
        </div>
      </DataCard>

      <DataCard eyebrow="Alerts" title="Notifications">
        <div className="form">
          <Toggle label="New high-impact insights" checked={notify.insights} onChange={(v) => setNotify({ ...notify, insights: v })} />
          <Toggle label="Failed runs and validation errors" checked={notify.failures} onChange={(v) => setNotify({ ...notify, failures: v })} />
          <Toggle label="Daily digest email" checked={notify.digest} onChange={(v) => setNotify({ ...notify, digest: v })} />
        </div>
      </DataCard>

      <DataCard className="danger" eyebrow="Danger zone" title="Reset workspace">
        <div className="row between wrap gap-s">
          <p className="muted sm" style={{ margin: 0 }}>Clears all runs, insights and history. Connected sources are kept.</p>
          <button className="btn btn-danger" onClick={() => setResetOpen(true)}>Reset workspace</button>
        </div>
      </DataCard>

      <Modal
        open={resetOpen}
        onClose={() => { setResetOpen(false); setConfirm('') }}
        eyebrow="Confirm"
        title="Reset this workspace?"
        width={440}
        footer={
          <>
            <button className="btn ghost" onClick={() => { setResetOpen(false); setConfirm('') }}>Cancel</button>
            <button className="btn btn-danger" disabled={confirm !== 'RESET'} onClick={() => { setResetOpen(false); setConfirm(''); toast({ kind: 'success', title: 'Workspace reset', body: 'Demo mode, nothing was deleted' }) }}>Reset</button>
          </>
        }
      >
        <p className="muted">This can't be undone. Type <b className="mono">RESET</b> to confirm.</p>
        <input className="input" autoFocus value={confirm} onChange={(e) => setConfirm(e.target.value)} aria-label="Type RESET to confirm" />
      </Modal>
    </div>
  )
}

function Toggle({ label, sub, checked, onChange }: { label: string; sub?: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="toggle-row">
      <input type="checkbox" className="switch" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <div><strong>{label}</strong>{sub && <span className="muted">{sub}</span>}</div>
    </label>
  )
}
