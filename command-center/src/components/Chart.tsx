import { useEffect, useId, useRef, useState } from 'react'

// Hand-rolled SVG charts: small, themeable, and trivially swappable for a chart
// library later. All colors are CSS variables so the theme drives them.

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [w, setW] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setW(Math.floor(e.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, w] as const
}

type Pt = [number, number]
function smooth(pts: Pt[]): string {
  if (!pts.length) return ''
  let d = `M${pts[0][0]},${pts[0][1]}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] ?? p2
    const t = 0.16
    d += ` C${p1[0] + (p2[0] - p0[0]) * t},${p1[1] + (p2[1] - p0[1]) * t} ${p2[0] - (p3[0] - p1[0]) * t},${p2[1] - (p3[1] - p1[1]) * t} ${p2[0]},${p2[1]}`
  }
  return d
}

export interface Series {
  label: string
  values: number[]
  color?: string
}
const palette = ['var(--accent)', 'var(--violet)', 'var(--info)']

export function LineChart({ series, labels, height = 220, format = (v) => Math.round(v).toLocaleString() }: {
  series: Series[]
  labels: string[]
  height?: number
  format?: (v: number) => string
}) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const id = useId().replace(/:/g, '')
  const [hover, setHover] = useState<number | null>(null)
  const pad = { t: 14, r: 10, b: 26, l: 44 }
  const all = series.flatMap((s) => s.values)
  const max = Math.max(...all) * 1.08
  const min = Math.min(...all) * 0.9
  const n = labels.length
  const iw = Math.max(1, w - pad.l - pad.r)
  const ih = height - pad.t - pad.b
  const x = (i: number) => pad.l + (n < 2 ? 0 : (i * iw) / (n - 1))
  const y = (v: number) => pad.t + ih - ((v - min) / (max - min || 1)) * ih
  const ticks = [0, 0.33, 0.66, 1].map((f) => min + (max - min) * f)
  const every = Math.ceil(n / Math.max(2, Math.floor(iw / 70)))

  return (
    <div
      ref={ref}
      className="chart"
      style={{ height }}
      onMouseLeave={() => setHover(null)}
      onMouseMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect()
        const i = Math.round(((e.clientX - r.left - pad.l) / iw) * (n - 1))
        setHover(i >= 0 && i < n ? i : null)
      }}
    >
      {w > 0 && (
        <svg width={w} height={height} role="img" aria-label={series.map((s) => s.label).join(', ')}>
          <defs>
            {series.map((s, k) => (
              <linearGradient key={k} id={`${id}g${k}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" style={{ stopColor: s.color ?? palette[k], stopOpacity: k ? 0.08 : 0.22 }} />
                <stop offset="1" style={{ stopColor: s.color ?? palette[k], stopOpacity: 0 }} />
              </linearGradient>
            ))}
          </defs>
          {ticks.map((t, i) => (
            <g key={i}>
              <line x1={pad.l} x2={w - pad.r} y1={y(t)} y2={y(t)} className="grid-line" />
              <text x={pad.l - 10} y={y(t)} className="axis" textAnchor="end" dominantBaseline="middle">{format(t)}</text>
            </g>
          ))}
          {labels.map((l, i) => i % every === 0 && (
            <text key={i} x={x(i)} y={height - 6} className="axis" textAnchor="middle">{l}</text>
          ))}
          {series.map((s, k) => {
            const pts = s.values.map((v, i) => [x(i), y(v)] as Pt)
            const line = smooth(pts)
            return (
              <g key={s.label}>
                <path d={`${line} L${x(n - 1)},${pad.t + ih} L${x(0)},${pad.t + ih} Z`} fill={`url(#${id}g${k})`} className="area" />
                <path d={line} className="line" style={{ stroke: s.color ?? palette[k], strokeDasharray: k ? '4 4' : undefined }} />
              </g>
            )
          })}
          {hover !== null && (
            <g>
              <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={pad.t + ih} className="crosshair" />
              {series.map((s, k) => <circle key={k} cx={x(hover)} cy={y(s.values[hover])} r={4} className="hover-dot" style={{ stroke: s.color ?? palette[k] }} />)}
            </g>
          )}
        </svg>
      )}
      {hover !== null && (
        <div className="chart-tip" style={{ left: Math.min(x(hover) + 12, w - 150) }}>
          <div className="mono xs muted">{labels[hover]}</div>
          {series.map((s, k) => (
            <div key={k} className="chart-tip-row">
              <i style={{ background: s.color ?? palette[k] }} />{s.label}<b>{format(s.values[hover])}</b>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function Sparkline({ values, color = 'var(--accent)', width = 84, height = 26 }: { values: number[]; color?: string; width?: number; height?: number }) {
  const max = Math.max(...values), min = Math.min(...values)
  const pts = values.map((v, i) => [(i / (values.length - 1)) * width, height - 2 - ((v - min) / (max - min || 1)) * (height - 4)] as Pt)
  return (
    <svg width={width} height={height} className="spark" aria-hidden>
      <path d={smooth(pts)} style={{ stroke: color }} />
      <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r={2.5} style={{ fill: color }} />
    </svg>
  )
}

// 7 x 24 activity heat grid.
export function ActivityGraph({ data, rowLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] }: { data: number[][]; rowLabels?: string[] }) {
  return (
    <div className="heat">
      {data.map((row, r) => (
        <div key={r} className="heat-row">
          <span className="axis-label">{rowLabels[r]}</span>
          <div className="heat-cells">
            {row.map((v, c) => (
              <i key={c} title={`${rowLabels[r]} ${String(c).padStart(2, '0')}:00 · ${Math.round(v * 100)} events`} style={{ opacity: 0.08 + v * 0.92 }} className={v > 0.82 ? 'hot' : ''} />
            ))}
          </div>
        </div>
      ))}
      <div className="heat-row">
        <span />
        <div className="heat-axis"><span>00</span><span>06</span><span>12</span><span>18</span><span>23</span></div>
      </div>
    </div>
  )
}

export function Ring({ value, size = 132, stroke = 10, label, sub }: { value: number; size?: number; stroke?: number; label?: string; sub?: string }) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const [shown, setShown] = useState(0)
  useEffect(() => { const t = requestAnimationFrame(() => setShown(value)); return () => cancelAnimationFrame(t) }, [value])
  return (
    <div className="ring" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} className="ring-track" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} className="ring-ticks" strokeWidth={stroke} strokeDasharray={`1 ${c / 60 - 1}`} />
        <circle cx={size / 2} cy={size / 2} r={r} className="ring-val" strokeWidth={stroke} strokeDasharray={c} strokeDashoffset={c * (1 - shown)} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      </svg>
      <div className="ring-center">
        <strong>{label ?? `${Math.round(value * 100)}%`}</strong>
        {sub && <span>{sub}</span>}
      </div>
    </div>
  )
}

export function Progress({ value, active, tone = 'accent' }: { value: number; active?: boolean; tone?: 'accent' | 'warn' | 'err' | 'violet' }) {
  return (
    <div className={`progress tone-${tone} ${active ? 'active' : ''}`} role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}>
      <i style={{ width: `${value}%` }} />
    </div>
  )
}
