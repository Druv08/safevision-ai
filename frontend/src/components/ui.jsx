import { useEffect, useRef, useState } from "react";
import {
  LuCircleAlert, LuCircleCheck, LuInfo, LuTriangleAlert, LuX, LuLoaderCircle,
  LuChevronLeft, LuChevronRight, LuUpload,
} from "react-icons/lu";
import { SEVERITY_TONE, STATUS_META } from "../theme";

/* ── Brand ─────────────────────────────────────────────────── */
export function Logo({ compact = false }) {
  return (
    <span className="flex items-center gap-2.5 min-w-0">
      <svg viewBox="0 0 32 32" className="w-8 h-8 flex-shrink-0" aria-hidden="true">
        <rect width="32" height="32" rx="8" className="fill-surface-2" />
        <path d="M16 5.5 25 9v6.6c0 5.4-3.7 9.6-9 11.4-5.3-1.8-9-6-9-11.4V9z" fill="none" className="stroke-primary" strokeWidth="2.2" strokeLinejoin="round" />
        <path d="m11.8 16.2 3 3 5.6-6" fill="none" className="stroke-primary" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {!compact && (
        <span className="font-semibold tracking-tight text-fg truncate">
          SafeVision<span className="text-primary">AI</span>
        </span>
      )}
    </span>
  );
}

/* ── Layout ────────────────────────────────────────────────── */
export function PageHeader({ title, description, actions }) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between mb-6">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-fg">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted max-w-2xl">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function SectionTitle({ title, description, action }) {
  return (
    <div className="flex items-start justify-between gap-3 mb-4">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold text-fg">{title}</h2>
        {description && <p className="text-xs text-muted mt-0.5">{description}</p>}
      </div>
      {action}
    </div>
  );
}

/* ── Feedback ──────────────────────────────────────────────── */
const ALERT_ICON = { danger: LuCircleAlert, warning: LuTriangleAlert, ok: LuCircleCheck, info: LuInfo };

export function Alert({ tone = "danger", title, children, onRetry, onClose, className = "" }) {
  const Icon = ALERT_ICON[tone];
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={`tone-${tone} flex items-start gap-3 rounded-lg border px-4 py-3 text-sm ${className}`}
      style={{
        background: "color-mix(in srgb, var(--tone) 9%, var(--surface))",
        borderColor: "color-mix(in srgb, var(--tone) 30%, transparent)",
      }}
    >
      <Icon className="mt-0.5 flex-shrink-0 text-base" style={{ color: "var(--tone)" }} aria-hidden="true" />
      <div className="flex-1 min-w-0 break-words text-fg">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={title ? "text-muted mt-0.5" : ""}>{children}</div>}
      </div>
      {onRetry && <button onClick={onRetry} className="btn btn-secondary btn-sm">Retry</button>}
      {onClose && (
        <button onClick={onClose} aria-label="Dismiss" className="btn btn-ghost btn-sm btn-icon -my-1">
          <LuX />
        </button>
      )}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children, action, className = "" }) {
  return (
    <div className={`flex flex-col items-center justify-center text-center px-6 py-12 ${className}`}>
      {Icon && (
        <div className="w-11 h-11 rounded-xl bg-surface-2 border border-line flex items-center justify-center mb-4 text-muted text-xl">
          <Icon aria-hidden="true" />
        </div>
      )}
      <p className="text-sm font-medium text-fg">{title}</p>
      {children && <p className="text-sm text-muted mt-1 max-w-sm">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Spinner({ className = "" }) {
  return <LuLoaderCircle className={`animate-spin ${className}`} aria-hidden="true" />;
}

export function PageFallback() {
  return (
    <div className="flex items-center justify-center py-24 text-muted text-2xl" role="status" aria-label="Loading">
      <Spinner />
    </div>
  );
}

/** value: 0–100, or null for an honest "working" bar with no fake percentage. */
export function ProgressBar({ value, label }) {
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value ?? undefined}
      className="h-1.5 w-full rounded-full bg-surface-2 overflow-hidden"
    >
      {value == null ? (
        <div className="h-full w-2/5 rounded-full bg-primary" style={{ animation: "sv-indeterminate 1.3s ease-in-out infinite" }} />
      ) : (
        <div className="h-full rounded-full bg-primary transition-[width] duration-200" style={{ width: `${value}%` }} />
      )}
    </div>
  );
}

/* ── Data display ──────────────────────────────────────────── */
export function StatCard({ label, value, icon: Icon, tone = "tone-neutral", hint, loading }) {
  return (
    <div className="card p-4 sm:p-5 min-w-0">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs sm:text-sm font-medium text-muted truncate">{label}</p>
        {Icon && (
          <span className={`${tone} w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0`}
            style={{ color: "var(--tone)", background: "color-mix(in srgb, var(--tone) 12%, transparent)" }}>
            <Icon aria-hidden="true" />
          </span>
        )}
      </div>
      {loading ? (
        <div className="skeleton h-8 w-20 mt-3" />
      ) : (
        <p className="mt-2 text-2xl sm:text-3xl font-semibold tracking-tight tabular-nums text-fg truncate">{value}</p>
      )}
      {hint && <p className="mt-1 text-xs text-muted truncate">{hint}</p>}
    </div>
  );
}

export function SeverityBadge({ severity }) {
  return <span className={`badge ${SEVERITY_TONE[severity] || "tone-neutral"}`}>{severity}</span>;
}

export function StatusBadge({ status }) {
  const meta = STATUS_META[status] || { label: status, tone: "tone-neutral" };
  return <span className={`badge ${meta.tone}`}><span className="dot" />{meta.label}</span>;
}

/* ── Controls ──────────────────────────────────────────────── */
export function Segmented({ value, onChange, options, label, size = "md" }) {
  return (
    <div role="group" aria-label={label} className="inline-flex p-0.5 rounded-lg bg-surface-2 border border-line">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={`${size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3 text-sm"} rounded-md font-medium transition-colors ${
            value === o.value ? "bg-surface text-fg shadow-sm border border-line" : "text-muted hover:text-fg border border-transparent"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Pagination({ page, pageSize, total, onChange }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-3 border-t border-line text-sm">
      <p className="text-muted tabular-nums">
        {from}–{to} of {total}
      </p>
      <div className="flex items-center gap-1">
        <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>
          <LuChevronLeft /> <span className="hidden sm:inline">Previous</span>
        </button>
        <span className="text-muted tabular-nums px-2">{page} / {pages}</span>
        <button className="btn btn-ghost btn-sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>
          <span className="hidden sm:inline">Next</span> <LuChevronRight />
        </button>
      </div>
    </div>
  );
}

/** Click, keyboard or drag-and-drop file picker. */
export function Dropzone({ accept, onFile, title, hint, disabled }) {
  const [over, setOver] = useState(false);
  const inputRef = useRef(null);
  const pick = (files) => { if (files?.[0]) onFile(files[0]); };
  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => { if (!disabled && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); inputRef.current?.click(); } }}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); if (!disabled) pick(e.dataTransfer.files); }}
      className={`flex flex-col items-center justify-center text-center rounded-xl border border-dashed px-6 py-12 cursor-pointer transition-colors ${
        over ? "border-primary bg-primary/5" : "border-line-strong hover:border-primary/60 hover:bg-surface-2/50"
      } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
    >
      <div className="w-11 h-11 rounded-xl bg-surface-2 border border-line flex items-center justify-center text-primary text-xl mb-4">
        <LuUpload aria-hidden="true" />
      </div>
      <p className="text-sm font-medium text-fg">{title}</p>
      <p className="text-xs text-muted mt-1">{hint}</p>
      <span className="btn btn-secondary btn-sm mt-4 pointer-events-none">Browse files</span>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="sr-only"
        tabIndex={-1}
        onChange={(e) => { pick(e.target.files); e.target.value = ""; }}
      />
    </div>
  );
}

/* ── Dialogs (native <dialog>: focus trap, Esc and top layer for free) ── */
export function Dialog({ open, onClose, title, description, children, footer, width = "32rem" }) {
  const ref = useRef(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      className="modal"
      style={{ "--modal-w": width }}
      onCancel={(e) => { e.preventDefault(); onClose(); }}
      onClick={(e) => { if (e.target === ref.current) onClose(); }}
      aria-labelledby="dialog-title"
    >
      {open && (
        <div className="flex flex-col max-h-[calc(100dvh-2rem)]">
          <div className="flex items-start justify-between gap-4 px-5 pt-5 pb-3">
            <div className="min-w-0">
              <h2 id="dialog-title" className="text-base font-semibold text-fg">{title}</h2>
              {description && <p className="text-sm text-muted mt-1">{description}</p>}
            </div>
            <button onClick={onClose} aria-label="Close" className="btn btn-ghost btn-sm btn-icon -mr-1.5 -mt-1">
              <LuX />
            </button>
          </div>
          <div className="px-5 pb-5 overflow-y-auto">{children}</div>
          {footer && <div className="flex flex-wrap justify-end gap-2 px-5 py-3.5 border-t border-line bg-surface-2/40">{footer}</div>}
        </div>
      )}
    </dialog>
  );
}

export function ConfirmDialog({ open, title, children, confirmLabel = "Confirm", danger, busy, onConfirm, onCancel }) {
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      title={title}
      width="26rem"
      footer={
        <>
          <button className="btn btn-secondary" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className={`btn ${danger ? "btn-danger" : "btn-primary"}`} onClick={onConfirm} disabled={busy}>
            {busy && <Spinner />} {confirmLabel}
          </button>
        </>
      }
    >
      <div className="text-sm text-muted">{children}</div>
    </Dialog>
  );
}
