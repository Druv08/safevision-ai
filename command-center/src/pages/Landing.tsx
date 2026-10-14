import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { RichText } from '../components/AI'
import { LineChart } from '../components/Chart'
import { Icon, Logo } from '../components/Icon'
import { IntelligenceCore } from '../components/IntelligenceCore'
import { MetricCard } from '../components/MetricCard'
import { StatusDot, SystemStatus } from '../components/StatusIndicator'
import { product, series } from '../data'

const capabilities = [
  { n: '01', title: 'Ingest', body: 'Connect streams, files and APIs. Nexa normalises everything into one live model of your world.', icon: 'data' as const },
  { n: '02', title: 'Reason', body: 'A continuous reasoning loop scores, clusters and explains change, and always cites its sources.', icon: 'intelligence' as const },
  { n: '03', title: 'Act', body: 'Recommendations become tasks, automations and decisions you can trace end to end.', icon: 'play' as const },
]

export function Landing() {
  // Last word of the headline gets the accent treatment, whatever the headline is.
  const words = product.headline.split(' ')
  const head = words.slice(0, -1).join(' ')
  const tail = words[words.length - 1]

  const [latency, setLatency] = useState(142)
  useEffect(() => { const iv = setInterval(() => setLatency(136 + Math.round(Math.random() * 14)), 2000); return () => clearInterval(iv) }, [])

  const labels = Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, '0')}:00`)

  return (
    <div className="landing">
      <header className="l-nav">
        <Link to="/" className="brand"><Logo /><span className="brand-name">{product.name}</span></Link>
        <nav className="l-links hide-mobile">
          <a href="#preview">Platform</a>
          <a href="#capabilities">Capabilities</a>
          <a href="#status">Status</a>
        </nav>
        <div className="row gap-s">
          <Link to="/app" className="btn ghost hide-mobile">Sign in</Link>
          <Link to="/app" className="btn btn-accent">Launch console</Link>
        </div>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <span className="hero-chip"><StatusDot state="operational" />All systems operational<span className="mono xs muted">v0.9 preview</span></span>
          <h1 className="display">{head} <span className="accent-word">{tail}</span></h1>
          <p className="hero-sub">{product.tagline}</p>
          <div className="hero-ctas">
            <Link to="/app" className="btn btn-accent lg">Enter command center<Icon name="arrowRight" size={16} /></Link>
            <a href="#preview" className="btn lg">See it think</a>
          </div>
          <dl className="hero-stats">
            <div><dt>Latency p95</dt><dd>{latency}<small>ms</small></dd></div>
            <div><dt>Uptime</dt><dd>99.98<small>%</small></dd></div>
            <div><dt>Sources live</dt><dd>4<small>/4</small></dd></div>
          </dl>
        </div>
        <div className="hero-visual">
          <IntelligenceCore />
          <span className="float-tag t1 mono"><i />ingest · 12.4k/s</span>
          <span className="float-tag t2 mono"><i className="v" />decision · E-114</span>
          <span className="float-tag t3 mono"><i />reasoning · model v4</span>
        </div>
      </section>

      <section id="status" className="l-status">
        <SystemStatus />
      </section>

      <section id="preview" className="l-section">
        <div className="l-section-head">
          <span className="eyebrow">The console</span>
          <h2>A live model of everything you care about.</h2>
          <p className="muted">Metrics, reasoning and recommended actions in one calm surface, built for operators.</p>
        </div>
        <div className="preview-frame">
          <div className="preview-bar"><i /><i /><i /><span className="mono xs muted">nexa.app / core / overview</span></div>
          <div className="preview-body">
            <div className="preview-metrics">
              <MetricCard label="Signals processed" value="2.14M" delta={18.2} trend={series(16, 40, 8, 2)} />
              <MetricCard label="Insight precision" value="87.4" unit="%" delta={0.6} trend={series(16, 40, 3, 6)} />
              <MetricCard label="p95 latency" value={latency} unit="ms" delta={-32.4} trend={series(16, 40, 6, 9).reverse()} />
            </div>
            <div className="preview-split">
              <div className="card"><div className="card-body"><LineChart labels={labels} series={[{ label: 'Signals', values: series(24, 1200, 220, 3) }, { label: 'Baseline', values: series(24, 1050, 90, 8) }]} height={200} /></div></div>
              <div className="card preview-ai">
                <div className="ai-query"><span className="mono accent">{'>'}</span> Why did Stream B spike?</div>
                <RichText text={'Volume rose **18%**, mostly in one 40-minute window, and lines up with **two upstream config changes**.\n- Spike explained, not anomalous\n- Schema drift needs attention'} />
                <div className="row gap-s"><span className="chip"><span className="mono xs src-n">1</span>Stream B</span><span className="chip"><span className="mono xs src-n">2</span>Config log</span></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="capabilities" className="l-section">
        <div className="caps">
          {capabilities.map((c) => (
            <article key={c.n} className="cap">
              <div className="row between"><span className="mono xs muted">{c.n}</span><Icon name={c.icon} size={18} /></div>
              <h3>{c.title}</h3>
              <p className="muted">{c.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="l-cta">
        <h2 className="display sm">Start with a question.</h2>
        <p className="muted">The command center is running with sample data. Press <kbd className="kbd">Ctrl</kbd> <kbd className="kbd">K</kbd> once you're inside.</p>
        <Link to="/app" className="btn btn-accent lg">Enter command center<Icon name="arrowRight" size={16} /></Link>
      </section>

      <footer className="l-foot mono xs muted">
        <span>{product.name} · Intelligence platform</span>
        <span>Build 0.9.0 · {new Date().getFullYear()}</span>
      </footer>
    </div>
  )
}
