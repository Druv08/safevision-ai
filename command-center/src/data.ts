// Domain-neutral models + mock data. When the real problem lands, rename the
// nouns here (Task, Insight, DataRecord, Source) and the whole UI follows.

export const product = {
  name: 'Nexa',
  headline: 'Intelligence, organized.',
  tagline:
    'One command center for every signal, model and decision. Nexa ingests your data, reasons over it continuously, and tells you what to do next.',
}

export type TaskStatus = 'queued' | 'running' | 'done' | 'failed'
export interface Task {
  id: string
  title: string
  status: TaskStatus
  progress: number
  owner: string
  tag: string
  updatedAt: number
}

export type Impact = 'high' | 'medium' | 'low'
export interface Insight {
  id: string
  title: string
  body: string
  confidence: number
  impact: Impact
  source: string
  at: number
}

export type EventKind = 'run' | 'insight' | 'sync' | 'alert' | 'user'
export interface ActivityEvent {
  id: string
  at: number
  kind: EventKind
  title: string
  detail: string
}

export type RecordStatus = 'active' | 'stale' | 'error'
export interface DataRecord {
  id: string
  name: string
  type: string
  status: RecordStatus
  quality: number
  rows: number
  updatedAt: number
}

export interface Source {
  id: string
  title: string
  kind: string
  snippet: string
}

export interface AIResponse {
  content: string
  sources: Source[]
  actions: string[]
  confidence: number
  trace: { step: string; ms: number }[]
}

export interface Workspace {
  id: string
  name: string
  env: string
}

export interface Notification {
  id: string
  title: string
  body: string
  at: number
  read: boolean
}

const MIN = 60_000
const now = Date.now()

export const workspaces: Workspace[] = [
  { id: 'core', name: 'Core Workspace', env: 'prod' },
  { id: 'lab', name: 'Research Lab', env: 'staging' },
  { id: 'sandbox', name: 'Sandbox', env: 'dev' },
]

export const currentProject = {
  code: 'PRJ-0427',
  name: 'Signal Analysis Run',
  description: 'Continuous reasoning over 4 connected streams with automated anomaly triage.',
}

export const seedTasks: Task[] = [
  { id: 't1', title: 'Ingest stream batch #2291', status: 'running', progress: 64, owner: 'Pipeline', tag: 'ingest', updatedAt: now - 2 * MIN },
  { id: 't2', title: 'Re-score entity graph', status: 'running', progress: 31, owner: 'Model v4', tag: 'model', updatedAt: now - 4 * MIN },
  { id: 't3', title: 'Cluster anomalies (window 6h)', status: 'queued', progress: 0, owner: 'Analyst', tag: 'analyze', updatedAt: now - 9 * MIN },
  { id: 't4', title: 'Generate daily brief', status: 'done', progress: 100, owner: 'Nexa', tag: 'report', updatedAt: now - 26 * MIN },
  { id: 't5', title: 'Validate schema drift', status: 'failed', progress: 48, owner: 'Pipeline', tag: 'quality', updatedAt: now - 41 * MIN },
]

export const insights: Insight[] = [
  { id: 'i1', title: 'Signal volume up 18% in Stream B', body: 'Increase is concentrated in a 40-minute window and correlates with two upstream configuration changes.', confidence: 0.92, impact: 'high', source: 'Stream B', at: now - 6 * MIN },
  { id: 'i2', title: 'Three entities share an unusual pattern', body: 'Entities E-114, E-208 and E-311 moved in lockstep across 5 consecutive intervals. Likely a shared upstream cause.', confidence: 0.81, impact: 'medium', source: 'Entity graph', at: now - 18 * MIN },
  { id: 'i3', title: 'Model confidence stable after retrain', body: 'Mean confidence held at 0.87 (±0.02) across the last 12 runs. No intervention needed.', confidence: 0.95, impact: 'low', source: 'Model v4', at: now - 52 * MIN },
  { id: 'i4', title: 'Schema drift in 2 fields', body: '`segment` and `region_code` changed type in the last sync. 1.2% of rows rejected.', confidence: 0.88, impact: 'high', source: 'Data quality', at: now - 64 * MIN },
  { id: 'i5', title: 'Processing latency trending down', body: 'p95 latency improved from 210ms to 142ms after queue rebalancing.', confidence: 0.9, impact: 'low', source: 'Runtime', at: now - 3 * 60 * MIN },
  { id: 'i6', title: 'Coverage gap in Stream D', body: 'No events received for 22 minutes during the overnight window. Check connector health.', confidence: 0.74, impact: 'medium', source: 'Stream D', at: now - 5 * 60 * MIN },
]

export const seedEvents: ActivityEvent[] = [
  { id: 'e1', at: now - 1 * MIN, kind: 'run', title: 'Batch #2291 ingest started', detail: '12,480 records queued' },
  { id: 'e2', at: now - 6 * MIN, kind: 'insight', title: 'New insight generated', detail: 'Signal volume up 18% in Stream B' },
  { id: 'e3', at: now - 11 * MIN, kind: 'sync', title: 'Source synced', detail: 'Stream A · 98% complete' },
  { id: 'e4', at: now - 19 * MIN, kind: 'user', title: 'Alex ran an analysis', detail: '"Compare last 24h vs baseline"' },
  { id: 'e5', at: now - 41 * MIN, kind: 'alert', title: 'Schema validation failed', detail: '2 fields changed type' },
  { id: 'e6', at: now - 63 * MIN, kind: 'run', title: 'Daily brief generated', detail: '6 insights · 2 actions' },
]

export const liveEventPool: Omit<ActivityEvent, 'id' | 'at'>[] = [
  { kind: 'sync', title: 'Source synced', detail: 'Stream C · 4,112 records' },
  { kind: 'insight', title: 'Pattern detected', detail: 'Recurring spike every ~45 min in Stream A' },
  { kind: 'run', title: 'Model re-scored entities', detail: '1,904 entities updated' },
  { kind: 'alert', title: 'Latency above threshold', detail: 'p95 crossed 200ms for 30s' },
  { kind: 'user', title: 'Sam pinned an insight', detail: 'Coverage gap in Stream D' },
]

export const timeline = [
  { id: 'tl1', time: '09:12', title: 'Run initialised', detail: 'Workspace snapshot captured', state: 'done' as const },
  { id: 'tl2', time: '09:14', title: 'Sources connected', detail: '4 streams · 2.1M records', state: 'done' as const },
  { id: 'tl3', time: '09:31', title: 'Model reasoning', detail: 'Scoring entity graph', state: 'active' as const },
  { id: 'tl4', time: '—', title: 'Insight synthesis', detail: 'Pending model output', state: 'pending' as const },
  { id: 'tl5', time: '—', title: 'Recommended actions', detail: 'Awaiting review', state: 'pending' as const },
]

const recordNames = ['Stream A', 'Stream B', 'Stream C', 'Stream D', 'Entity graph', 'Reference set', 'Event log', 'Feedback loop', 'Model outputs', 'Annotations', 'Archive 2025', 'External feed']
const recordTypes = ['stream', 'stream', 'stream', 'stream', 'graph', 'table', 'log', 'table', 'table', 'table', 'archive', 'api']
export const records: DataRecord[] = recordNames.map((name, i) => ({
  id: `R-${(1000 + i * 37).toString(36).toUpperCase()}`,
  name,
  type: recordTypes[i],
  status: i === 3 ? 'error' : i % 5 === 4 ? 'stale' : 'active',
  quality: [0.98, 0.94, 0.97, 0.61, 0.89, 0.99, 0.92, 0.85, 0.96, 0.78, 0.7, 0.9][i],
  rows: Math.round(1e4 * (1 + ((i * 7919) % 97))),
  updatedAt: now - (i * 17 + 3) * MIN,
}))

export const seedNotifications: Notification[] = [
  { id: 'n1', title: 'Insight ready', body: 'Signal volume up 18% in Stream B', at: now - 6 * MIN, read: false },
  { id: 'n2', title: 'Validation failed', body: 'Schema drift detected in 2 fields', at: now - 41 * MIN, read: false },
  { id: 'n3', title: 'Daily brief', body: 'Your brief for today is ready', at: now - 63 * MIN, read: true },
]

export const suggestedPrompts = [
  'Summarize what changed in the last 24 hours',
  'Why did Stream B spike?',
  'What should I prioritise next?',
  'Compare this run against baseline',
]

// Deterministic pseudo-random series so charts look real but stay stable.
export function series(n: number, base: number, vol: number, seed = 1): number[] {
  let s = seed
  const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647)
  let v = base
  return Array.from({ length: n }, (_, i) => {
    v += (rnd() - 0.48) * vol + Math.sin(i / 3) * vol * 0.25
    return Math.max(0, Math.round(v))
  })
}

export function heat(rows: number, cols: number, seed = 7): number[][] {
  const s = series(rows * cols, 50, 30, seed)
  const max = Math.max(...s)
  return Array.from({ length: rows }, (_, r) => s.slice(r * cols, r * cols + cols).map((v) => v / max))
}

export function ago(ts: number): string {
  const s = Math.max(1, Math.round((Date.now() - ts) / 1000))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  return `${Math.round(s / 86400)}d ago`
}

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

const sourcePool: Source[] = [
  { id: 's1', title: 'Stream B · events', kind: 'stream', snippet: 'Volume 14,220 → 16,780 between 08:40–09:20.' },
  { id: 's2', title: 'Config change log', kind: 'log', snippet: 'Two upstream parameter changes at 08:37.' },
  { id: 's3', title: 'Entity graph v12', kind: 'graph', snippet: '3 entities with correlated movement (r=0.91).' },
  { id: 's4', title: 'Run history', kind: 'table', snippet: '12 prior runs, mean confidence 0.87.' },
  { id: 's5', title: 'Data quality report', kind: 'report', snippet: '1.2% rows rejected due to schema drift.' },
]

const answers: ((q: string) => string)[] = [
  (q) => `Here's what I found for **"${q}"**.\n\nAcross 4 connected sources, overall signal volume rose **18%** over the last 6 hours. Most of the change is concentrated in Stream B and lines up with two upstream configuration changes at 08:37.\n- Stream B: +2,560 events in a 40-minute window\n- Entity graph: 3 entities moving in lockstep (r = 0.91)\n- Data quality: 1.2% rows rejected from schema drift\n\nThe spike looks **explained, not anomalous**. The schema drift is the item that needs attention.`,
  (q) => `Short answer to **"${q}"**: prioritise the schema drift, then the coverage gap.\n- **Fix schema drift** in \`segment\` and \`region_code\`. It is silently dropping 1.2% of rows.\n- **Check the Stream D connector.** There's a 22-minute gap overnight.\n- **Leave the model as is.** Confidence has been stable across 12 runs.\n\nI can open a task for each of these.`,
  (q) => `Compared with the baseline window, this run is **healthier overall** (re: "${q}").\n- Throughput **+11%**, p95 latency **−32%** (210ms → 142ms)\n- Insight precision held at **0.87**\n- One regression: rejected rows went from 0.1% to **1.2%**\n\nApart from the data-quality regression, the run is better than baseline.`,
]

let turn = 0
export async function askAI(prompt: string): Promise<AIResponse> {
  await wait(1400 + Math.random() * 900)
  if (/fail|error/i.test(prompt)) throw new Error('Model endpoint timed out after 30s. No tokens were consumed.')
  const pick = /priorit|next|should/i.test(prompt) ? 1 : /compar|baseline/i.test(prompt) ? 2 : turn++ % 3
  return {
    content: answers[pick](prompt.trim()),
    sources: sourcePool.slice(pick, pick + 3),
    actions: pick === 1 ? ['Create 2 tasks', 'Open data quality'] : ['Create task', 'Pin insight'],
    confidence: [0.91, 0.86, 0.88][pick],
    trace: [
      { step: 'Parsed intent', ms: 38 },
      { step: 'Retrieved context · 3 sources', ms: 412 },
      { step: 'Reasoned over 2.1M records', ms: 960 },
      { step: 'Synthesised answer', ms: 274 },
    ],
  }
}
