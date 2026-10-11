import { useState } from 'react'
import { ActivityFeed } from '../components/ActivityFeed'
import { DataCard, Segmented } from '../components/DataCard'
import { Timeline } from '../components/Timeline'
import { timeline, type EventKind } from '../data'
import { useStore } from '../store'
import { StatusDot } from '../components/StatusIndicator'

const kinds = ['all', 'run', 'insight', 'sync', 'alert', 'user'] as const

export function Activity() {
  const { events } = useStore()
  const [kind, setKind] = useState<(typeof kinds)[number]>('all')
  const list = kind === 'all' ? events : events.filter((e) => e.kind === (kind as EventKind))
  return (
    <div className="page">
      <section className="page-head">
        <div>
          <div className="eyebrow">Activity</div>
          <h1>Event stream</h1>
          <p className="lede">Every run, sync, insight and human action in this workspace, as it happens.</p>
        </div>
        <StatusDot state="processing" label="Streaming live" />
      </section>
      <div className="grid">
        <DataCard className="span-8" title="All events" actions={<Segmented value={kind} options={kinds} onChange={setKind} />} pad={false}>
          <ActivityFeed events={list} />
        </DataCard>
        <DataCard className="span-4" eyebrow="Current run" title="Timeline">
          <Timeline items={timeline} />
        </DataCard>
      </div>
    </div>
  )
}
