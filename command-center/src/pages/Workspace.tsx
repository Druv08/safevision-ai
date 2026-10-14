import { useState } from 'react'
import { AIConsole } from '../components/AI'
import { DataCard } from '../components/DataCard'
import { Icon } from '../components/Icon'
import { Timeline } from '../components/Timeline'
import { currentProject, timeline } from '../data'
import { useStore } from '../store'

// The primary workspace. This is the slot that becomes the hackathon feature:
// swap <AIConsole/> for a camera feed, map, document viewer, etc.
export function Workspace() {
  const { messages } = useStore()
  const [sources, setSources] = useState([
    { name: 'Stream A', on: true },
    { name: 'Stream B', on: true },
    { name: 'Entity graph v12', on: true },
    { name: 'Run history', on: true },
    { name: 'External feed', on: false },
  ])
  const active = sources.filter((s) => s.on)
  const queries = messages.filter((m) => m.role === 'user').length

  return (
    <div className="page page-workspace">
      <section className="page-head compact">
        <div>
          <div className="eyebrow">{currentProject.code} · Workspace</div>
          <h1>Intelligence workspace</h1>
        </div>
        <span className="mono xs muted hide-mobile">{queries} {queries === 1 ? 'query' : 'queries'} this session</span>
      </section>
      <div className="workspace-grid">
        <AIConsole context={[`${active.length} sources`, 'Overview']} />
        <div className="workspace-side hide-tablet">
          <DataCard eyebrow="Grounding" title="Context sources">
            <ul className="src-list">
              {sources.map((s, i) => (
                <li key={s.name}>
                  <label className="src-toggle">
                    <input type="checkbox" className="switch sm" checked={s.on} onChange={() => setSources((all) => all.map((x, j) => (j === i ? { ...x, on: !x.on } : x)))} />
                    <Icon name={i < 2 ? 'sync' : 'file'} size={14} />
                    <span>{s.name}</span>
                  </label>
                </li>
              ))}
            </ul>
          </DataCard>
          <DataCard eyebrow="Run" title="Progress">
            <Timeline items={timeline} />
          </DataCard>
        </div>
      </div>
    </div>
  )
}
