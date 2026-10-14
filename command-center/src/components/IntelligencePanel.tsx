import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ago, insights } from '../data'
import { useStore } from '../store'
import { Icon } from './Icon'
import { Segmented } from './DataCard'
import { Timeline } from './Timeline'
import { timeline } from '../data'

const tabs = ['Insights', 'Context', 'Queue'] as const

// Right-hand context rail: what the AI currently believes about this view.
export function IntelligencePanel() {
  const s = useStore()
  const nav = useNavigate()
  const [tab, setTab] = useState<(typeof tabs)[number]>('Insights')
  const [q, setQ] = useState('')

  return (
    <aside className={`intel ${s.panelOpen ? 'open' : ''}`} aria-label="Intelligence panel">
      <div className="intel-head">
        <div className="intel-title">
          <span className="orb" />
          <strong>Context</strong>
          <span className="mono xs muted">live</span>
        </div>
        <button className="icon-btn sm" onClick={() => s.setPanelOpen(false)} aria-label="Close panel"><Icon name="x" size={14} /></button>
      </div>

      <form className="intel-ask" onSubmit={(e) => { e.preventDefault(); if (!q.trim()) return; s.setPendingPrompt(q.trim()); setQ(''); nav('/app/workspace') }}>
        <Icon name="spark" size={14} />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about this view..." aria-label="Ask about this view" />
        <button type="submit" className="icon-btn sm" aria-label="Ask" disabled={!q.trim()}><Icon name="arrowRight" size={14} /></button>
      </form>

      <Segmented value={tab} options={tabs} onChange={setTab} />

      <div className="intel-body" key={tab}>
        {tab === 'Insights' && (
          <>
            <div className="next-action">
              <span className="label accent">Recommended next action</span>
              <strong>Resolve schema drift before the next sync</strong>
              <p>2 fields changed type and 1.2% of rows are being dropped. Fixing this restores full coverage.</p>
              <div className="row gap-s">
                <button className="btn btn-accent sm" onClick={() => { s.addTask('Fix schema drift', 'quality'); s.toast({ kind: 'success', title: 'Task created', body: 'Fix schema drift' }) }}>Create task</button>
                <button className="btn ghost sm" onClick={() => s.toast({ kind: 'info', title: 'Snoozed for 1 hour' })}>Snooze</button>
              </div>
            </div>
            {insights.slice(0, 4).map((i) => (
              <article key={i.id} className={`insight impact-${i.impact}`}>
                <div className="insight-top">
                  <span className={`pill pill-${i.impact}`}>{i.impact}</span>
                  <span className="mono xs muted">{ago(i.at)}</span>
                </div>
                <strong>{i.title}</strong>
                <p>{i.body}</p>
                <div className="conf-bar"><i><em style={{ width: `${i.confidence * 100}%` }} /></i><span className="mono xs">{Math.round(i.confidence * 100)}%</span></div>
              </article>
            ))}
          </>
        )}
        {tab === 'Context' && (
          <>
            <p className="muted sm">Nexa is grounding answers in these sources for the current view.</p>
            {['Stream A', 'Stream B', 'Entity graph v12', 'Run history'].map((c, i) => (
              <div key={c} className="ctx-item">
                <Icon name={i < 2 ? 'sync' : 'file'} size={14} />
                <span>{c}</span>
                <span className="mono xs muted">{[98, 100, 100, 94][i]}%</span>
              </div>
            ))}
            <div className="label" style={{ marginTop: 18 }}>Run timeline</div>
            <Timeline items={timeline} />
          </>
        )}
        {tab === 'Queue' && (
          <>
            {s.tasks.slice(0, 6).map((t) => (
              <div key={t.id} className="queue-item">
                <span className={`qdot q-${t.status}`} />
                <div>
                  <strong>{t.title}</strong>
                  <span className="mono xs muted">{t.status} · {Math.round(t.progress)}%</span>
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </aside>
  )
}
