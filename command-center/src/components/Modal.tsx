import { useEffect, useRef, type ReactNode } from 'react'
import { Icon } from './Icon'

// Native <dialog> gives us focus trapping, Esc-to-close and a top layer for free.
export function Modal({ open, onClose, title, eyebrow, children, footer, width = 520 }: {
  open: boolean
  onClose: () => void
  title: string
  eyebrow?: string
  children: ReactNode
  footer?: ReactNode
  width?: number
}) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) {
      d.showModal()
      // showModal() focuses the first focusable (the close button); prefer the first field.
      d.querySelector<HTMLElement>('.modal-body :is(input, select, textarea)')?.focus()
    }
    if (!open && d.open) d.close()
  }, [open])
  return (
    <dialog ref={ref} className="modal" style={{ width }} onClose={onClose} onClick={(e) => e.target === ref.current && onClose()}>
      {open && (
        <div className="modal-inner">
          <header className="modal-head">
            <div>
              {eyebrow && <div className="eyebrow">{eyebrow}</div>}
              <h2>{title}</h2>
            </div>
            <button className="icon-btn" onClick={onClose} aria-label="Close"><Icon name="x" /></button>
          </header>
          <div className="modal-body">{children}</div>
          {footer && <footer className="modal-foot">{footer}</footer>}
        </div>
      )}
    </dialog>
  )
}
