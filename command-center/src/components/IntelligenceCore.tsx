import { useEffect, useRef } from 'react'

// Animated centerpiece: sources orbit a reasoning core; particles are data flowing in,
// pulses flowing out are decisions. Pure canvas, ~0 deps, honours reduced motion.
const ACCENT = '198,242,78'
const VIOLET = '140,123,255'

export function IntelligenceCore({ className = '' }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current!
    const ctx = canvas.getContext('2d')!
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
    let w = 0, h = 0, raf = 0
    const resize = () => {
      const r = canvas.getBoundingClientRect()
      const dpr = Math.min(devicePixelRatio || 1, 2)
      w = r.width; h = r.height
      canvas.width = w * dpr; canvas.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      if (reduce) draw(0)
    }
    const ro = new ResizeObserver(resize)
    ro.observe(canvas)

    const orbits = [
      { r: 0.2, n: 5, speed: 0.00011, dash: false },
      { r: 0.32, n: 8, speed: -0.00007, dash: true },
      { r: 0.45, n: 11, speed: 0.00004, dash: false },
    ]
    const nodes = orbits.flatMap((o, oi) => Array.from({ length: o.n }, (_, i) => ({ oi, a: (i / o.n) * Math.PI * 2 + oi, violet: (i + oi) % 6 === 0 })))
    type P = { node: number; t: number; v: number; out: boolean; bend: number }
    const parts: P[] = []

    const pos = (n: (typeof nodes)[number], time: number, R: number, cx: number, cy: number) => {
      const o = orbits[n.oi]
      const a = n.a + time * o.speed
      return [cx + Math.cos(a) * o.r * R * 1.25, cy + Math.sin(a) * o.r * R * 0.78] as const
    }

    function draw(time: number) {
      ctx.clearRect(0, 0, w, h)
      const cx = w / 2, cy = h / 2, R = Math.min(w, h * 1.25)
      // Orbits (ellipses give the scene depth).
      orbits.forEach((o) => {
        ctx.beginPath()
        ctx.setLineDash(o.dash ? [2, 6] : [])
        ctx.strokeStyle = 'rgba(255,255,255,0.07)'
        ctx.ellipse(cx, cy, o.r * R * 1.25, o.r * R * 0.78, 0, 0, Math.PI * 2)
        ctx.stroke()
      })
      ctx.setLineDash([])
      // Spokes.
      nodes.forEach((n) => {
        const [x, y] = pos(n, time, R, cx, cy)
        const g = ctx.createLinearGradient(x, y, cx, cy)
        g.addColorStop(0, 'rgba(255,255,255,0.05)')
        g.addColorStop(1, 'rgba(255,255,255,0)')
        ctx.strokeStyle = g
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(cx, cy); ctx.stroke()
      })
      // Particles.
      if (!reduce && Math.random() < 0.22) parts.push({ node: (Math.random() * nodes.length) | 0, t: 0, v: 0.006 + Math.random() * 0.008, out: Math.random() < 0.18, bend: (Math.random() - 0.5) * 0.6 })
      for (let i = parts.length - 1; i >= 0; i--) {
        const p = parts[i]
        p.t += p.v
        if (p.t >= 1) { parts.splice(i, 1); continue }
        const [nx, ny] = pos(nodes[p.node], time, R, cx, cy)
        const [sx, sy, ex, ey] = p.out ? [cx, cy, nx, ny] : [nx, ny, cx, cy]
        const mx = (sx + ex) / 2 - (ey - sy) * p.bend, my = (sy + ey) / 2 + (ex - sx) * p.bend
        const at = (t: number) => [(1 - t) ** 2 * sx + 2 * (1 - t) * t * mx + t * t * ex, (1 - t) ** 2 * sy + 2 * (1 - t) * t * my + t * t * ey]
        const [x, y] = at(p.t)
        const [tx, ty] = at(Math.max(0, p.t - 0.08))
        const alpha = Math.sin(p.t * Math.PI)
        const c = p.out ? VIOLET : ACCENT
        const g = ctx.createLinearGradient(tx, ty, x, y)
        g.addColorStop(0, `rgba(${c},0)`)
        g.addColorStop(1, `rgba(${c},${alpha * 0.9})`)
        ctx.strokeStyle = g
        ctx.lineWidth = 1.6
        ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(x, y); ctx.stroke()
        ctx.fillStyle = `rgba(${c},${alpha})`
        ctx.beginPath(); ctx.arc(x, y, 1.6, 0, Math.PI * 2); ctx.fill()
      }
      ctx.lineWidth = 1
      // Nodes.
      nodes.forEach((n) => {
        const [x, y] = pos(n, time, R, cx, cy)
        const c = n.violet ? VIOLET : n.oi === 0 ? ACCENT : '255,255,255'
        const a = n.oi === 0 ? 0.9 : 0.55
        ctx.fillStyle = `rgba(${c},${a * 0.15})`
        ctx.beginPath(); ctx.arc(x, y, 7, 0, Math.PI * 2); ctx.fill()
        ctx.fillStyle = `rgba(${c},${a})`
        ctx.beginPath(); ctx.arc(x, y, 2.4, 0, Math.PI * 2); ctx.fill()
      })
      // Core: breathing glow + rotating arcs.
      const pulse = reduce ? 0.5 : (Math.sin(time / 900) + 1) / 2
      const core = R * 0.075
      const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, core * (3.2 + pulse))
      glow.addColorStop(0, `rgba(${ACCENT},0.55)`)
      glow.addColorStop(0.35, `rgba(${ACCENT},0.12)`)
      glow.addColorStop(1, `rgba(${ACCENT},0)`)
      ctx.fillStyle = glow
      ctx.beginPath(); ctx.arc(cx, cy, core * (3.2 + pulse), 0, Math.PI * 2); ctx.fill()
      ctx.fillStyle = '#0b0d10'
      ctx.beginPath(); ctx.arc(cx, cy, core, 0, Math.PI * 2); ctx.fill()
      ctx.strokeStyle = `rgba(${ACCENT},0.9)`
      ctx.lineWidth = 1.5
      for (let k = 0; k < 3; k++) {
        const a0 = time / (700 + k * 300) * (k % 2 ? -1 : 1) + k * 2
        ctx.beginPath(); ctx.arc(cx, cy, core + 6 + k * 6, a0, a0 + 0.9 + k * 0.4); ctx.globalAlpha = 0.8 - k * 0.22; ctx.stroke()
      }
      ctx.globalAlpha = 1
      ctx.lineWidth = 1
      ctx.fillStyle = `rgba(${ACCENT},1)`
      ctx.beginPath(); ctx.arc(cx, cy, core * 0.42, 0, Math.PI * 2); ctx.fill()
    }

    const loop = (t: number) => { draw(t); raf = requestAnimationFrame(loop) }
    if (!reduce) raf = requestAnimationFrame(loop)
    return () => { cancelAnimationFrame(raf); ro.disconnect() }
  }, [])

  return <canvas ref={ref} className={`core-canvas ${className}`} aria-hidden />
}
