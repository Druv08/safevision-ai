import type { ReactNode } from 'react'

// The universal module container. Every panel in the app is a DataCard, so swapping
// a chart for a map, a video feed or a document viewer is just a change of children.
export function DataCard({ title, eyebrow, actions, children, footer, className = '', glow, pad = true }: {
  title?: ReactNode
  eyebrow?: ReactNode
  actions?: ReactNode
  children: ReactNode
  footer?: ReactNode
  className?: string
  glow?: boolean
  pad?: boolean
}) {
  return (
    <section className={`card ${glow ? 'card-glow' : ''} ${className}`}>
      {(title || actions || eyebrow) && (
        <header className="card-head">
          <div>
            {eyebrow && <div className="eyebrow">{eyebrow}</div>}
            {title && <h3>{title}</h3>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      <div className={pad ? 'card-body' : 'card-flush'}>{children}</div>
      {footer && <footer className="card-foot">{footer}</footer>}
    </section>
  )
}

export function Segmented<T extends string>({ value, options, onChange }: { value: T; options: readonly T[]; onChange: (v: T) => void }) {
  return (
    <div className="seg" role="tablist">
      {options.map((o) => (
        <button key={o} role="tab" aria-selected={o === value} className={o === value ? 'on' : ''} onClick={() => onChange(o)}>{o}</button>
      ))}
    </div>
  )
}
