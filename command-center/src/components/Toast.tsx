import { useStore } from '../store'
import { Icon } from './Icon'

const icons = { success: 'check', info: 'info', error: 'alert' } as const

export function Toaster() {
  const { toasts, dismissToast } = useStore()
  return (
    <div className="toaster" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.kind}`}>
          <span className="toast-icon"><Icon name={icons[t.kind]} size={14} /></span>
          <div className="toast-text">
            <strong>{t.title}</strong>
            {t.body && <span>{t.body}</span>}
          </div>
          <button className="icon-btn sm" onClick={() => dismissToast(t.id)} aria-label="Dismiss"><Icon name="x" size={14} /></button>
          <i className="toast-timer" />
        </div>
      ))}
    </div>
  )
}
