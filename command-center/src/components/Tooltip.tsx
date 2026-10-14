import type { ReactNode } from 'react'

// CSS-only tooltip: shows on hover and keyboard focus.
export function Tooltip({ label, children, side = 'bottom' }: { label: ReactNode; children: ReactNode; side?: 'top' | 'bottom' | 'right' }) {
  return (
    <span className={`tip tip-${side}`}>
      {children}
      <span className="tip-bubble" role="tooltip">{label}</span>
    </span>
  )
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="kbd">{children}</kbd>
}

export const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)
export const modKey = isMac ? '⌘' : 'Ctrl'
