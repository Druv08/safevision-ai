import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type Dispatch, type ReactNode, type SetStateAction } from 'react'
import { liveEventPool, seedEvents, seedNotifications, seedTasks, workspaces, type ActivityEvent, type AIResponse, type Notification, type Task } from './data'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  at: number
  prompt?: string
  res?: AIResponse
  error?: string
}

export type ToastKind = 'success' | 'info' | 'error'
export interface ToastT {
  id: number
  kind: ToastKind
  title: string
  body?: string
}

interface Store {
  toasts: ToastT[]
  toast: (t: Omit<ToastT, 'id'>) => void
  dismissToast: (id: number) => void
  paletteOpen: boolean
  setPaletteOpen: (v: boolean) => void
  createOpen: boolean
  setCreateOpen: (v: boolean) => void
  panelOpen: boolean
  setPanelOpen: (v: boolean) => void
  workspaceId: string
  setWorkspaceId: (id: string) => void
  tasks: Task[]
  addTask: (title: string, tag: string, run?: boolean) => void
  runTask: (id: string) => void
  aiBusy: boolean
  setAiBusy: (v: boolean) => void
  pendingPrompt: string | null
  setPendingPrompt: (p: string | null) => void
  /** Read-and-clear, so a prompt is only ever sent once even if effects re-run. */
  takePendingPrompt: () => string | null
  notifications: Notification[]
  markAllRead: () => void
  events: ActivityEvent[]
  messages: ChatMessage[]
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>
}

const Ctx = createContext<Store | null>(null)
let toastId = 0

export function StoreProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastT[]>([])
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [panelOpen, setPanelOpen] = useState(() => window.innerWidth >= 1280)
  const [workspaceId, setWorkspaceId] = useState(workspaces[0].id)
  const [tasks, setTasks] = useState(seedTasks)
  const [aiBusy, setAiBusy] = useState(false)
  const [pendingPrompt, setPendingState] = useState<string | null>(null)
  const pendingRef = useRef<string | null>(null)
  const setPendingPrompt = useCallback((p: string | null) => { pendingRef.current = p; setPendingState(p) }, [])
  const takePendingPrompt = useCallback(() => { const p = pendingRef.current; pendingRef.current = null; setPendingState(null); return p }, [])
  const [notifications, setNotifications] = useState(seedNotifications)
  const [events, setEvents] = useState(seedEvents)
  const [messages, setMessages] = useState<ChatMessage[]>([])

  // Simulated live event stream.
  useEffect(() => {
    let i = 0
    const iv = setInterval(() => {
      const e = liveEventPool[i++ % liveEventPool.length]
      setEvents((all) => [{ ...e, id: `live${Date.now()}`, at: Date.now() }, ...all].slice(0, 40))
    }, 11_000)
    return () => clearInterval(iv)
  }, [])

  const dismissToast = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), [])
  const toast = useCallback(
    (t: Omit<ToastT, 'id'>) => {
      const id = ++toastId
      setToasts((all) => [...all.slice(-3), { ...t, id }])
      setTimeout(() => dismissToast(id), 4200)
    },
    [dismissToast],
  )

  const addTask = useCallback((title: string, tag: string, run = false) => {
    setTasks((t) => [{ id: `t${Date.now()}${t.length}`, title, tag, status: run ? 'running' : 'queued', progress: 0, owner: 'You', updatedAt: Date.now() }, ...t])
  }, [])

  const runTask = useCallback((id: string) => {
    setTasks((t) => t.map((x) => (x.id === id ? { ...x, status: 'running', progress: x.status === 'done' ? 0 : x.progress, updatedAt: Date.now() } : x)))
  }, [])

  // One shared clock advances every running task, so progress bars move everywhere at once.
  useEffect(() => {
    const iv = setInterval(() => {
      setTasks((all) => {
        if (!all.some((t) => t.status === 'running')) return all
        return all.map((t) => {
          if (t.status !== 'running') return t
          const progress = Math.min(100, t.progress + 2 + Math.random() * 6)
          return { ...t, progress, status: progress >= 100 ? 'done' : 'running', updatedAt: Date.now() }
        })
      })
    }, 900)
    return () => clearInterval(iv)
  }, [])

  // Announce completions.
  const doneKey = tasks.filter((t) => t.status === 'done').map((t) => t.id).join()
  const [seenDone, setSeenDone] = useState(doneKey)
  useEffect(() => {
    if (doneKey === seenDone) return
    const prev = new Set(seenDone.split(','))
    tasks.filter((t) => t.status === 'done' && !prev.has(t.id)).forEach((t) => toast({ kind: 'success', title: 'Task complete', body: t.title }))
    setSeenDone(doneKey)
  }, [doneKey, seenDone, tasks, toast])

  const markAllRead = useCallback(() => setNotifications((n) => n.map((x) => ({ ...x, read: true }))), [])

  const value = useMemo(
    () => ({ toasts, toast, dismissToast, paletteOpen, setPaletteOpen, createOpen, setCreateOpen, panelOpen, setPanelOpen, workspaceId, setWorkspaceId, tasks, addTask, runTask, aiBusy, setAiBusy, pendingPrompt, setPendingPrompt, takePendingPrompt, notifications, markAllRead, events, messages, setMessages }),
    [toasts, toast, dismissToast, paletteOpen, createOpen, panelOpen, workspaceId, tasks, addTask, runTask, aiBusy, pendingPrompt, setPendingPrompt, takePendingPrompt, notifications, markAllRead, events, messages],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useStore() {
  const s = useContext(Ctx)
  if (!s) throw new Error('useStore must be used inside <StoreProvider>')
  return s
}
