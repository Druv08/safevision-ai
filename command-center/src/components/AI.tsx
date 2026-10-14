import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react'
import { askAI, suggestedPrompts } from '../data'
import { useStore, type ChatMessage } from '../store'
import { Icon, Logo } from './Icon'
import { Tooltip } from './Tooltip'

/* ---------- tiny markdown: paragraphs, "- " bullets, **bold**, `code` ---------- */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) =>
    part.startsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong>
      : part.startsWith('`') ? <code key={i}>{part.slice(1, -1)}</code>
        : <Fragment key={i}>{part}</Fragment>,
  )
}
export function RichText({ text }: { text: string }) {
  const blocks: ReactNode[] = []
  let bullets: string[] = []
  const flush = () => { if (bullets.length) blocks.push(<ul key={blocks.length}>{bullets.map((b, i) => <li key={i}>{inline(b)}</li>)}</ul>); bullets = [] }
  text.split('\n').forEach((line) => {
    if (line.startsWith('- ')) bullets.push(line.slice(2))
    else { flush(); if (line.trim()) blocks.push(<p key={blocks.length}>{inline(line)}</p>) }
  })
  flush()
  return <div className="rich">{blocks}</div>
}

/* ---------- AIInput ---------- */
const modes = ['Ask', 'Analyze', 'Run'] as const
export type AIMode = (typeof modes)[number]

export function AIInput({ onSubmit, busy, onStop, context, autoFocus, placeholder }: {
  onSubmit: (text: string, mode: AIMode) => void
  busy?: boolean
  onStop?: () => void
  context?: string[]
  autoFocus?: boolean
  placeholder?: string
}) {
  const [text, setText] = useState('')
  const [mode, setMode] = useState<AIMode>('Ask')
  const ref = useRef<HTMLTextAreaElement>(null)
  useEffect(() => { if (autoFocus) ref.current?.focus() }, [autoFocus])
  useEffect(() => {
    const el = ref.current
    if (el) { el.style.height = 'auto'; el.style.height = `${Math.min(el.scrollHeight, 160)}px` }
  }, [text])
  const submit = () => {
    if (!text.trim() || busy) return
    onSubmit(text.trim(), mode)
    setText('')
  }
  return (
    <form className={`ai-input ${busy ? 'busy' : ''}`} onSubmit={(e) => { e.preventDefault(); submit() }}>
      <div className="ai-input-row">
        <span className="ai-prompt-glyph mono" aria-hidden>{'>'}</span>
        <textarea
          ref={ref}
          rows={1}
          value={text}
          placeholder={placeholder ?? 'Ask Nexa anything about this workspace...'}
          aria-label="Message Nexa"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
        />
        {busy ? (
          <button type="button" className="send stop" onClick={onStop} aria-label="Stop generating"><Icon name="stop" size={14} /></button>
        ) : (
          <button type="submit" className="send" disabled={!text.trim()} aria-label="Send"><Icon name="arrowUp" size={16} /></button>
        )}
      </div>
      <div className="ai-input-meta">
        <div className="ai-modes">
          {modes.map((m) => <button type="button" key={m} className={m === mode ? 'on' : ''} onClick={() => setMode(m)}>{m}</button>)}
        </div>
        <div className="ai-context">
          {context?.map((c) => <span key={c} className="chip chip-ghost"><Icon name="link" size={11} />{c}</span>)}
        </div>
        <span className="mono xs muted hide-mobile">Enter to send · Shift+Enter newline</span>
      </div>
    </form>
  )
}

/* ---------- Thinking state ---------- */
const thinkSteps = ['Parsing intent', 'Retrieving context', 'Reasoning over sources', 'Synthesising answer']
export function AIThinking() {
  const [step, setStep] = useState(0)
  useEffect(() => { const iv = setInterval(() => setStep((s) => Math.min(s + 1, thinkSteps.length - 1)), 520); return () => clearInterval(iv) }, [])
  return (
    <div className="ai-msg ai-assistant thinking" aria-live="polite">
      <div className="ai-avatar"><span className="orb" /></div>
      <div className="ai-body">
        <div className="ai-scan" />
        <ol className="think-steps">
          {thinkSteps.map((s, i) => (
            <li key={s} className={i < step ? 'done' : i === step ? 'active' : ''}>
              <span className="think-mark">{i < step ? <Icon name="check" size={11} /> : <i />}</span>{s}
            </li>
          ))}
        </ol>
      </div>
    </div>
  )
}

/* ---------- AIMessage ---------- */
export function AIMessage({ msg, onRegenerate, onAction }: { msg: ChatMessage; onRegenerate?: () => void; onAction?: (a: string) => void }) {
  const { toast } = useStore()
  const [openSource, setOpenSource] = useState<string | null>(null)
  const [traceOpen, setTraceOpen] = useState(false)
  // Typewriter only for brand-new answers; history renders instantly.
  const fresh = Date.now() - msg.at < 1200
  const [shown, setShown] = useState(fresh ? 0 : msg.content.length)
  useEffect(() => {
    if (shown >= msg.content.length) return
    const t = setTimeout(() => setShown((n) => n + 6), 12)
    return () => clearTimeout(t)
  }, [shown, msg.content.length])
  const streaming = shown < msg.content.length

  if (msg.role === 'user') {
    return (
      <div className="ai-msg ai-user">
        <div className="ai-query"><span className="mono accent">{'>'}</span> {msg.content}</div>
      </div>
    )
  }

  if (msg.error) {
    return (
      <div className="ai-msg ai-assistant ai-error">
        <div className="ai-avatar err"><Icon name="alert" size={14} /></div>
        <div className="ai-body">
          <strong>Request failed</strong>
          <p className="mono xs">{msg.error}</p>
          {onRegenerate && <button className="btn sm" onClick={onRegenerate}><Icon name="refresh" size={13} /> Try again</button>}
        </div>
      </div>
    )
  }

  const res = msg.res!
  const total = res.trace.reduce((a, t) => a + t.ms, 0)
  return (
    <div className="ai-msg ai-assistant">
      <div className="ai-avatar"><Logo size={22} /></div>
      <div className="ai-body">
        <div className="ai-meta mono xs">
          <button className="trace-toggle" onClick={() => setTraceOpen((v) => !v)} aria-expanded={traceOpen}>
            <Icon name="chevronRight" size={11} className={traceOpen ? 'rot' : ''} /> Reasoned for {(total / 1000).toFixed(2)}s
          </button>
          <span className="conf">confidence <b>{Math.round(res.confidence * 100)}%</b><i><em style={{ width: `${res.confidence * 100}%` }} /></i></span>
        </div>
        {traceOpen && (
          <ol className="trace mono xs">
            {res.trace.map((t) => <li key={t.step}><span>{t.step}</span><span>{t.ms}ms</span></li>)}
          </ol>
        )}
        <RichText text={msg.content.slice(0, shown)} />
        {streaming && <span className="caret" />}
        {!streaming && (
          <>
            <div className="ai-sources">
              <span className="label">Sources</span>
              {res.sources.map((s, i) => (
                <button key={s.id} className={`chip ${openSource === s.id ? 'on' : ''}`} onClick={() => setOpenSource(openSource === s.id ? null : s.id)}>
                  <span className="mono xs src-n">{i + 1}</span>{s.title}
                </button>
              ))}
            </div>
            {openSource && (() => {
              const s = res.sources.find((x) => x.id === openSource)!
              return <div className="source-peek"><span className="mono xs muted">{s.kind}</span><p>{s.snippet}</p></div>
            })()}
            <div className="ai-actions">
              {res.actions.map((a) => (
                <button key={a} className="btn sm btn-accent-ghost" onClick={() => onAction?.(a)}><Icon name="spark" size={13} />{a}</button>
              ))}
              <span className="spacer" />
              <Tooltip label="Copy" side="top">
                <button className="icon-btn sm" aria-label="Copy answer" onClick={() => { navigator.clipboard?.writeText(msg.content).catch(() => {}); toast({ kind: 'info', title: 'Copied to clipboard' }) }}><Icon name="copy" size={14} /></button>
              </Tooltip>
              <Tooltip label="Regenerate" side="top">
                <button className="icon-btn sm" aria-label="Regenerate answer" onClick={onRegenerate}><Icon name="refresh" size={14} /></button>
              </Tooltip>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

/* ---------- AIConsole: composes everything; drop it into any module ---------- */
export function AIConsole({ context = ['Overview', '4 sources'], compact, title = 'Intelligence' }: { context?: string[]; compact?: boolean; title?: string }) {
  const { messages, setMessages, aiBusy, setAiBusy, pendingPrompt, takePendingPrompt, addTask, toast } = useStore()
  const [busy, setBusy] = useState(false)
  const reqId = useRef(0)
  const endRef = useRef<HTMLDivElement>(null)

  const run = async (prompt: string, replaceId?: string) => {
    const id = ++reqId.current
    setBusy(true)
    setAiBusy(true)
    let msg: ChatMessage
    try {
      const res = await askAI(prompt)
      msg = { id: `a${Date.now()}`, role: 'assistant', content: res.content, res, prompt, at: Date.now() }
    } catch (e) {
      msg = { id: `a${Date.now()}`, role: 'assistant', content: '', prompt, error: (e as Error).message, at: Date.now() }
    }
    if (id !== reqId.current) return // stopped or superseded
    setMessages((m) => (replaceId ? m.map((x) => (x.id === replaceId ? msg : x)) : [...m, msg]))
    setBusy(false)
    setAiBusy(false)
  }

  const send = (text: string) => {
    setMessages((m) => [...m, { id: `u${Date.now()}`, role: 'user', content: text, at: Date.now() }])
    run(text)
  }
  const stop = () => { reqId.current++; setBusy(false); setAiBusy(false); toast({ kind: 'info', title: 'Generation stopped' }) }

  useEffect(() => {
    const p = takePendingPrompt()
    if (p) send(p)
  }, [pendingPrompt])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages.length, busy])

  const onAction = (a: string) => {
    if (/task/i.test(a)) {
      const n = /2/.test(a) ? 2 : 1
      for (let i = 0; i < n; i++) addTask(n > 1 ? ['Fix schema drift', 'Check Stream D connector'][i] : 'Follow up on AI insight', 'ai')
      toast({ kind: 'success', title: `${n} task${n > 1 ? 's' : ''} created`, body: 'Added to the queue from the AI response' })
    } else toast({ kind: 'info', title: a, body: 'Action dispatched' })
  }

  return (
    <div className={`ai-console ${compact ? 'compact' : ''} ${busy || aiBusy ? 'is-busy' : ''}`}>
      <header className="ai-head">
        <div className="ai-head-title">
          <span className="orb" />
          <div>
            <strong>{title}</strong>
            <span className="mono xs muted">{busy ? 'reasoning...' : 'model v4 · ready'}</span>
          </div>
        </div>
        {messages.length > 0 && <button className="btn ghost sm" onClick={() => setMessages([])}>Clear</button>}
      </header>
      <div className="ai-stream">
        {messages.length === 0 && !busy && (
          <div className="ai-intro">
            <h3>What should we figure out?</h3>
            <p className="muted">Nexa reasons over every connected source in this workspace and cites what it uses.</p>
            <div className="suggestions">
              {suggestedPrompts.map((p) => (
                <button key={p} className="suggestion" onClick={() => send(p)}>
                  <Icon name="spark" size={13} /><span>{p}</span><Icon name="arrowRight" size={13} className="go" />
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <AIMessage
            key={m.id}
            msg={m}
            onAction={onAction}
            onRegenerate={m.role === 'assistant' && m.prompt && !busy && i === messages.length - 1 ? () => run(m.prompt!, m.id) : undefined}
          />
        ))}
        {busy && <AIThinking />}
        <div ref={endRef} />
      </div>
      <AIInput onSubmit={send} busy={busy} onStop={stop} context={context} />
    </div>
  )
}
