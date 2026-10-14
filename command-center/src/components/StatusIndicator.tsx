import { useStore } from '../store'

export type SystemState = 'operational' | 'processing' | 'degraded' | 'down' | 'idle'

export function StatusDot({ state, label }: { state: SystemState; label?: string }) {
  return (
    <span className={`status status-${state}`}>
      <i className="dot" />
      {label && <span>{label}</span>}
    </span>
  )
}

// The four-cell system strip. Values derive from live store state.
export function SystemStatus({ sync = 98, compact = false }: { sync?: number; compact?: boolean }) {
  const { tasks, aiBusy } = useStore()
  const running = tasks.filter((t) => t.status === 'running').length
  return (
    <div className={`sys ${compact ? 'sys-compact' : ''}`}>
      <div className="sys-cell">
        <span className="label">System status</span>
        <StatusDot state="operational" label="Operational" />
        <Bars n={12} active={12} />
      </div>
      <div className="sys-cell">
        <span className="label">Processing</span>
        <strong className="sys-val">{21 + running}<small> tasks</small></strong>
        <Bars n={12} active={Math.min(12, running * 3 + 4)} pulse />
      </div>
      <div className="sys-cell">
        <span className="label">Intelligence</span>
        <StatusDot state={aiBusy ? 'processing' : 'operational'} label={aiBusy ? 'Reasoning' : 'Active'} />
        <span className="wave" data-busy={aiBusy}><i /><i /><i /><i /><i /></span>
      </div>
      <div className="sys-cell">
        <span className="label">Data sync</span>
        <strong className="sys-val">{sync}<small>%</small></strong>
        <span className="meter"><i style={{ width: `${sync}%` }} /></span>
      </div>
    </div>
  )
}

function Bars({ n, active, pulse }: { n: number; active: number; pulse?: boolean }) {
  return (
    <span className={`bars ${pulse ? 'bars-pulse' : ''}`}>
      {Array.from({ length: n }, (_, i) => <i key={i} className={i < active ? 'on' : ''} style={{ animationDelay: `${i * 80}ms` }} />)}
    </span>
  )
}
