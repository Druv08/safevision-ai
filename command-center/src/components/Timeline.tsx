export interface TimelineItem {
  id: string
  time: string
  title: string
  detail?: string
  state: 'done' | 'active' | 'pending'
}

export function Timeline({ items }: { items: TimelineItem[] }) {
  return (
    <ol className="timeline">
      {items.map((it) => (
        <li key={it.id} className={`tl tl-${it.state}`}>
          <span className="tl-time mono">{it.time}</span>
          <span className="tl-node" />
          <div className="tl-body">
            <strong>{it.title}</strong>
            {it.detail && <span>{it.detail}</span>}
          </div>
        </li>
      ))}
    </ol>
  )
}
