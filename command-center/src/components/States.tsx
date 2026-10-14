import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon'

export function EmptyState({ icon = 'inbox', title, body, action }: { icon?: IconName; title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="state">
      <div className="state-icon"><Icon name={icon} size={20} /></div>
      <h3>{title}</h3>
      {body && <p>{body}</p>}
      {action}
    </div>
  )
}

export function ErrorState({ title = 'Something went wrong', body, onRetry }: { title?: string; body?: string; onRetry?: () => void }) {
  return (
    <div className="state state-error">
      <div className="state-icon"><Icon name="alert" size={20} /></div>
      <h3>{title}</h3>
      {body && <p className="mono xs">{body}</p>}
      {onRetry && <button className="btn" onClick={onRetry}><Icon name="refresh" size={14} /> Retry</button>}
    </div>
  )
}

export function LoadingState({ label = 'Loading', rows = 4 }: { label?: string; rows?: number }) {
  return (
    <div className="loading" aria-busy="true" aria-label={label}>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skel-row">
          <Skeleton w={28} h={28} r={8} />
          <div style={{ flex: 1, display: 'grid', gap: 6 }}>
            <Skeleton w={`${60 - i * 7}%`} h={10} />
            <Skeleton w={`${35 + i * 5}%`} h={8} />
          </div>
        </div>
      ))}
    </div>
  )
}

export function Skeleton({ w = '100%', h = 12, r = 6 }: { w?: number | string; h?: number | string; r?: number }) {
  return <span className="skel" style={{ width: w, height: h, borderRadius: r }} />
}
