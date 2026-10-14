import { useEffect, useRef, useState } from 'react'
import { Sparkline } from './Chart'

export function MetricCard({ label, value, unit, delta, trend, hint }: {
  label: string
  value: number | string
  unit?: string
  delta?: number
  trend?: number[]
  hint?: string
}) {
  // Flash briefly when the value changes so live updates are noticeable but quiet.
  const [flash, setFlash] = useState(false)
  const first = useRef(true)
  useEffect(() => {
    if (first.current) { first.current = false; return }
    setFlash(true)
    const t = setTimeout(() => setFlash(false), 700)
    return () => clearTimeout(t)
  }, [value])
  const up = (delta ?? 0) >= 0
  return (
    <div className={`metric ${flash ? 'flash' : ''}`}>
      <div className="metric-top">
        <span className="label">{label}</span>
        {delta !== undefined && <span className={`delta ${up ? 'up' : 'down'}`}>{up ? '▲' : '▼'} {Math.abs(delta).toFixed(1)}%</span>}
      </div>
      <div className="metric-val">{value}{unit && <small>{unit}</small>}</div>
      <div className="metric-bottom">
        {hint && <span className="muted mono xs">{hint}</span>}
        {trend && <Sparkline values={trend} color={up ? 'var(--accent)' : 'var(--warn)'} />}
      </div>
    </div>
  )
}
