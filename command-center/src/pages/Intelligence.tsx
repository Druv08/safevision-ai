import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Segmented } from '../components/DataCard'
import { Icon } from '../components/Icon'
import { EmptyState } from '../components/States'
import { Tooltip } from '../components/Tooltip'
import { ago, insights } from '../data'
import { useStore } from '../store'

const filters = ['All', 'High', 'Medium', 'Low', 'Pinned'] as const

export function Intelligence() {
  const s = useStore()
  const nav = useNavigate()
  const [filter, setFilter] = useState<(typeof filters)[number]>('All')
  const [pinned, setPinned] = useState<string[]>([])
  const list = insights.filter((i) => filter === 'All' || (filter === 'Pinned' ? pinned.includes(i.id) : i.impact === filter.toLowerCase()))

  return (
    <div className="page">
      <section className="page-head">
        <div>
          <div className="eyebrow">Intelligence</div>
          <h1>Insights</h1>
          <p className="lede">Everything Nexa has concluded from your sources, ranked by impact and confidence.</p>
        </div>
        <Segmented value={filter} options={filters} onChange={setFilter} />
      </section>
      {list.length === 0 ? (
        <div className="card">
          <EmptyState
            icon="pin"
            title={filter === 'Pinned' ? 'No pinned insights yet' : 'Nothing matches this filter'}
            body={filter === 'Pinned' ? 'Pin an insight to keep it here for your team.' : 'Try a different impact level.'}
            action={<button className="btn" onClick={() => setFilter('All')}>Show all insights</button>}
          />
        </div>
      ) : (
        <div className="insight-grid">
          {list.map((i) => (
            <article key={i.id} className={`card insight-card impact-${i.impact}`}>
              <div className="insight-top">
                <span className={`pill pill-${i.impact}`}>{i.impact} impact</span>
                <span className="mono xs muted">{i.source} · {ago(i.at)}</span>
              </div>
              <h3>{i.title}</h3>
              <p className="muted">{i.body}</p>
              <div className="conf-bar"><i><em style={{ width: `${i.confidence * 100}%` }} /></i><span className="mono xs">{Math.round(i.confidence * 100)}% confidence</span></div>
              <div className="row gap-s">
                <button className="btn sm" onClick={() => { s.setPendingPrompt(`Explain: ${i.title}`); nav('/app/workspace') }}><Icon name="spark" size={13} />Explain</button>
                <button className="btn ghost sm" onClick={() => { s.addTask(`Follow up: ${i.title}`, 'analyze'); s.toast({ kind: 'success', title: 'Task created' }) }}>Create task</button>
                <span className="spacer" />
                <Tooltip label={pinned.includes(i.id) ? 'Unpin' : 'Pin'} side="top">
                  <button
                    className={`icon-btn sm ${pinned.includes(i.id) ? 'on' : ''}`}
                    aria-pressed={pinned.includes(i.id)}
                    aria-label="Pin insight"
                    onClick={() => setPinned((p) => (p.includes(i.id) ? p.filter((x) => x !== i.id) : [...p, i.id]))}
                  >
                    <Icon name="pin" size={14} />
                  </button>
                </Tooltip>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
