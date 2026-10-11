import { useEffect, useState } from 'react'
import { ago, type ActivityEvent, type EventKind } from '../data'
import { Icon, type IconName } from './Icon'
import { EmptyState } from './States'

const kindIcon: Record<EventKind, IconName> = { run: 'play', insight: 'spark', sync: 'sync', alert: 'alert', user: 'user' }

export function ActivityFeed({ events, limit }: { events: ActivityEvent[]; limit?: number }) {
  // Re-render every 30s so relative times stay honest.
  const [, tick] = useState(0)
  useEffect(() => { const iv = setInterval(() => tick((n) => n + 1), 30_000); return () => clearInterval(iv) }, [])
  const list = limit ? events.slice(0, limit) : events
  if (!list.length) return <EmptyState icon="activity" title="No activity yet" body="Events from runs, syncs and teammates will stream in here." />
  return (
    <ul className="feed">
      {list.map((e) => (
        <li key={e.id} className={`feed-item kind-${e.kind}`}>
          <span className="feed-icon"><Icon name={kindIcon[e.kind]} size={14} /></span>
          <div className="feed-body">
            <strong>{e.title}</strong>
            <span>{e.detail}</span>
          </div>
          <time className="mono xs muted">{ago(e.at)}</time>
        </li>
      ))}
    </ul>
  )
}
