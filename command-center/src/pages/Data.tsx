import { useCallback, useEffect, useState } from 'react'
import { Progress, Ring } from '../components/Chart'
import { Icon } from '../components/Icon'
import { Modal } from '../components/Modal'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { Segmented } from '../components/DataCard'
import { ago, records, type DataRecord } from '../data'
import { useStore } from '../store'

const statuses = ['all', 'active', 'stale', 'error'] as const
type Phase = 'loading' | 'ready' | 'error'

export function Data() {
  const { toast } = useStore()
  const [phase, setPhase] = useState<Phase>('loading')
  const [q, setQ] = useState('')
  const [status, setStatus] = useState<(typeof statuses)[number]>('all')
  const [open, setOpen] = useState<DataRecord | null>(null)

  // Simulated fetch. `fail` lets the demo show the error state on demand.
  const load = useCallback((fail = false) => {
    setPhase('loading')
    setTimeout(() => setPhase(fail ? 'error' : 'ready'), 900)
  }, [])
  useEffect(() => load(), [load])

  const list = records.filter((r) => (status === 'all' || r.status === status) && `${r.name} ${r.id} ${r.type}`.toLowerCase().includes(q.toLowerCase()))

  return (
    <div className="page">
      <section className="page-head">
        <div>
          <div className="eyebrow">Data</div>
          <h1>Sources</h1>
          <p className="lede">Connected sources, their health, and how much Nexa trusts them.</p>
        </div>
        <div className="page-actions">
          <button className="btn ghost" onClick={() => load(true)}>Simulate outage</button>
          <button className="btn" onClick={() => load()} disabled={phase === 'loading'}><Icon name="refresh" size={14} className={phase === 'loading' ? 'spin' : ''} />Refresh</button>
        </div>
      </section>

      <div className="card">
        <div className="toolbar">
          <label className="search-field">
            <Icon name="search" size={15} />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter sources..." aria-label="Filter sources" />
            {q && <button className="icon-btn sm" onClick={() => setQ('')} aria-label="Clear filter"><Icon name="x" size={13} /></button>}
          </label>
          <Segmented value={status} options={statuses} onChange={setStatus} />
        </div>

        {phase === 'loading' && <LoadingState label="Loading sources" rows={6} />}
        {phase === 'error' && <ErrorState title="Couldn't reach the data service" body="GET /v1/sources → 503 Service Unavailable (trace 7f3a-91c2)" onRetry={() => load()} />}
        {phase === 'ready' && list.length === 0 && (
          <EmptyState icon="search" title="No sources match" body={`Nothing found for "${q || status}".`} action={<button className="btn" onClick={() => { setQ(''); setStatus('all') }}>Clear filters</button>} />
        )}
        {phase === 'ready' && list.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr><th>Source</th><th>Type</th><th>Status</th><th>Quality</th><th className="num">Rows</th><th className="num">Updated</th></tr>
              </thead>
              <tbody>
                {list.map((r) => (
                  <tr key={r.id} onClick={() => setOpen(r)} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setOpen(r)}>
                    <td><strong>{r.name}</strong><span className="mono xs muted">{r.id}</span></td>
                    <td><span className="chip chip-ghost mono xs">{r.type}</span></td>
                    <td><span className={`pill pill-${r.status}`}>{r.status}</span></td>
                    <td><div className="q-cell"><Progress value={r.quality * 100} tone={r.quality < 0.75 ? 'warn' : 'accent'} /><span className="mono xs">{Math.round(r.quality * 100)}</span></div></td>
                    <td className="num mono">{r.rows.toLocaleString()}</td>
                    <td className="num mono muted">{ago(r.updatedAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal
        open={!!open}
        onClose={() => setOpen(null)}
        eyebrow={open ? `${open.type} · ${open.id}` : ''}
        title={open?.name ?? ''}
        footer={
          <>
            <button className="btn ghost" onClick={() => setOpen(null)}>Close</button>
            <button className="btn btn-accent" onClick={() => { toast({ kind: 'success', title: 'Resync started', body: open?.name }); setOpen(null) }}><Icon name="sync" size={14} />Resync source</button>
          </>
        }
      >
        {open && (
          <div className="detail">
            <Ring value={open.quality} sub="quality" size={116} />
            <dl className="detail-stats">
              <div><dt>Status</dt><dd><span className={`pill pill-${open.status}`}>{open.status}</span></dd></div>
              <div><dt>Rows</dt><dd className="mono">{open.rows.toLocaleString()}</dd></div>
              <div><dt>Last update</dt><dd className="mono">{ago(open.updatedAt)}</dd></div>
              <div><dt>Used in answers</dt><dd className="mono">{Math.round(open.quality * 40)}× today</dd></div>
            </dl>
            {open.status === 'error' && <p className="callout err"><Icon name="alert" size={14} />Connector stopped responding 22 minutes ago. Resync to retry.</p>}
          </div>
        )}
      </Modal>
    </div>
  )
}
