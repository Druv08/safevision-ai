import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ActivityFeed } from '../components/ActivityFeed'
import { ActivityGraph, LineChart, Progress, Ring } from '../components/Chart'
import { DataCard, Segmented } from '../components/DataCard'
import { Icon } from '../components/Icon'
import { MetricCard } from '../components/MetricCard'
import { Skeleton } from '../components/States'
import { StatusDot, SystemStatus } from '../components/StatusIndicator'
import { ago, currentProject, heat, insights, series, suggestedPrompts, workspaces } from '../data'
import { useStore } from '../store'

const ranges = ['24h', '7d', '30d'] as const
type Range = (typeof ranges)[number]
const rangeCfg: Record<Range, { n: number; label: (i: number) => string; seed: number }> = {
  '24h': { n: 24, label: (i) => `${String(i).padStart(2, '0')}:00`, seed: 3 },
  '7d': { n: 7, label: (i) => ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i], seed: 11 },
  '30d': { n: 30, label: (i) => `D${i + 1}`, seed: 29 },
}

export function Overview() {
  const s = useStore()
  const nav = useNavigate()
  const ws = workspaces.find((w) => w.id === s.workspaceId)!

  // Live metrics: nudge values every few seconds to show the system is alive.
  const [m, setM] = useState({ signals: 2_148_302, entities: 18_431, precision: 87.4, latency: 142 })
  useEffect(() => {
    const iv = setInterval(() => setM((p) => ({
      signals: p.signals + Math.round(800 + Math.random() * 1600),
      entities: p.entities + Math.round(Math.random() * 12),
      precision: +(p.precision + (Math.random() - 0.5) * 0.4).toFixed(1),
      latency: Math.round(138 + Math.random() * 12),
    })), 3200)
    return () => clearInterval(iv)
  }, [])

  // Range switch shows a short skeleton, as a real fetch would.
  const [range, setRange] = useState<Range>('24h')
  const [loading, setLoading] = useState(false)
  const changeRange = (r: Range) => { setRange(r); setLoading(true); setTimeout(() => setLoading(false), 650) }
  const cfg = rangeCfg[range]
  const chart = useMemo(() => ({
    labels: Array.from({ length: cfg.n }, (_, i) => cfg.label(i)),
    series: [
      { label: 'Signals', values: series(cfg.n, 1200, 220, cfg.seed) },
      { label: 'Baseline', values: series(cfg.n, 1050, 90, cfg.seed + 5) },
    ],
  }), [cfg])
  const heatData = useMemo(() => heat(7, 24), [])

  const running = s.tasks.filter((t) => t.status === 'running')
  const avg = s.tasks.reduce((a, t) => a + t.progress, 0) / (s.tasks.length || 1) / 100

  return (
    <div className="page">
      <section className="page-head">
        <div>
          <div className="eyebrow">{currentProject.code} · {ws.name}</div>
          <h1>{currentProject.name}</h1>
          <p className="lede">{currentProject.description}</p>
        </div>
        <div className="page-actions">
          <span className="run-pill"><StatusDot state="processing" label="Running" /><span className="mono xs muted">step 3/5</span></span>
          <button className="btn" onClick={() => s.setCreateOpen(true)}><Icon name="plus" size={15} />New task</button>
          <button className="btn btn-accent" onClick={() => { s.addTask('Ad-hoc analysis run', 'analyze', true); s.toast({ kind: 'info', title: 'Analysis started', body: 'Progress is tracked in the task queue' }) }}>
            <Icon name="play" size={13} />Run analysis
          </button>
        </div>
      </section>

      {/* Mobile-first focus entry: on phones the AI is the primary surface. */}
      <button className="focus-ask show-mobile" onClick={() => nav('/app/workspace')}>
        <span className="orb" />
        <div><strong>Ask Nexa</strong><span>{suggestedPrompts[0]}</span></div>
        <Icon name="arrowRight" size={16} />
      </button>

      <SystemStatus />

      <div className="metrics">
        <MetricCard label="Signals processed" value={m.signals.toLocaleString()} delta={18.2} trend={series(16, 40, 8, 2)} hint="last 24h" />
        <MetricCard label="Active entities" value={m.entities.toLocaleString()} delta={4.1} trend={series(16, 40, 5, 4)} hint="tracked" />
        <MetricCard label="Insight precision" value={m.precision} unit="%" delta={0.6} trend={series(16, 40, 3, 6)} hint="rolling 12 runs" />
        <MetricCard label="p95 latency" value={m.latency} unit="ms" delta={-32.4} trend={series(16, 40, 6, 9).reverse()} hint="vs 210ms baseline" />
      </div>

      <div className="grid">
        <DataCard
          className="span-8"
          eyebrow="Signal flow"
          title="Volume vs. baseline"
          actions={<Segmented value={range} options={ranges} onChange={changeRange} />}
          footer={<div className="legend"><span><i className="lg-accent" />Signals</span><span><i className="lg-violet dashed" />Baseline</span><span className="spacer" /><span className="mono xs muted">updated {ago(Date.now() - 4000)}</span></div>}
        >
          {loading ? <div className="chart-skel"><Skeleton h={220} r={10} /></div> : <LineChart series={chart.series} labels={chart.labels} height={240} />}
        </DataCard>

        <DataCard className="span-4" eyebrow="Run" title="Completion">
          <div className="ring-wrap">
            <Ring value={avg} sub="overall" />
            <div className="stack">
              {[['Ingest', 0.92, 'accent'], ['Reasoning', 0.64, 'violet'], ['Synthesis', 0.18, 'accent']].map(([l, v, tone]) => (
                <div key={l as string} className="prog-line">
                  <div className="row between"><span className="sm">{l}</span><span className="mono xs muted">{Math.round((v as number) * 100)}%</span></div>
                  <Progress value={(v as number) * 100} active={(v as number) < 1} tone={tone as 'accent' | 'violet'} />
                </div>
              ))}
            </div>
          </div>
        </DataCard>

        <DataCard
          className="span-7"
          eyebrow="Intelligence"
          title="AI insights"
          glow
          actions={<button className="btn ghost sm" onClick={() => nav('/app/intelligence')}>View all<Icon name="arrowRight" size={13} /></button>}
        >
          <div className="next-action wide">
            <div>
              <span className="label accent"><Icon name="spark" size={12} /> Recommended next action</span>
              <strong>Resolve schema drift before the next sync</strong>
              <p>Two fields changed type upstream. Fixing them restores 1.2% of dropped rows and lifts coverage back to 100%.</p>
            </div>
            <div className="row gap-s">
              <button className="btn btn-accent sm" onClick={() => { s.addTask('Fix schema drift', 'quality', true); s.toast({ kind: 'success', title: 'Fix started', body: 'Fix schema drift' }) }}>Apply fix</button>
              <button className="btn sm" onClick={() => { s.setPendingPrompt('Why is schema drift the top priority?'); nav('/app/workspace') }}>Ask why</button>
            </div>
          </div>
          <div className="insight-list">
            {insights.slice(0, 3).map((i) => (
              <div key={i.id} className="insight-row">
                <span className={`pill pill-${i.impact}`}>{i.impact}</span>
                <div><strong>{i.title}</strong><span className="muted sm">{i.body}</span></div>
                <span className="mono xs muted">{Math.round(i.confidence * 100)}%</span>
              </div>
            ))}
          </div>
        </DataCard>

        <DataCard
          className="span-5"
          eyebrow={`${running.length} running`}
          title="Task queue"
          actions={<button className="icon-btn sm" onClick={() => s.setCreateOpen(true)} aria-label="New task"><Icon name="plus" size={14} /></button>}
          pad={false}
        >
          <ul className="tasks">
            {s.tasks.slice(0, 6).map((t) => (
              <li key={t.id} className={`task task-${t.status}`}>
                <span className={`qdot q-${t.status}`} />
                <div className="task-main">
                  <div className="row between">
                    <strong>{t.title}</strong>
                    <span className="mono xs muted">{t.status === 'running' ? `${Math.round(t.progress)}%` : t.status}</span>
                  </div>
                  <Progress value={t.progress} active={t.status === 'running'} tone={t.status === 'failed' ? 'err' : 'accent'} />
                  <span className="mono xs muted">{t.tag} · {t.owner} · {ago(t.updatedAt)}</span>
                </div>
                {(t.status === 'queued' || t.status === 'failed') && (
                  <button className="btn sm" onClick={() => s.runTask(t.id)}>{t.status === 'failed' ? <><Icon name="refresh" size={12} />Retry</> : <><Icon name="play" size={11} />Run</>}</button>
                )}
              </li>
            ))}
          </ul>
        </DataCard>

        <DataCard className="span-7 hide-mobile" eyebrow="Activity" title="Load by hour" actions={<span className="mono xs muted">last 7 days</span>}>
          <ActivityGraph data={heatData} />
        </DataCard>

        <DataCard className="span-5" eyebrow="Live" title="Activity feed" actions={<button className="btn ghost sm" onClick={() => nav('/app/activity')}>All<Icon name="arrowRight" size={13} /></button>} pad={false}>
          <ActivityFeed events={s.events} limit={5} />
        </DataCard>
      </div>
    </div>
  )
}
