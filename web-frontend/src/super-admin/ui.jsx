import { useEffect, useRef, useState } from 'react'
import { ToastCtx } from './api'

const BTN = {
  primary: 'bg-primary text-on-primary hover:bg-primary-hover border-transparent',
  outline: 'border-outline text-primary hover:bg-primary-container/60',
  text: 'border-transparent text-primary hover:bg-primary-container/60',
  danger: 'bg-error text-on-error border-transparent hover:opacity-90',
}

export function Button({ variant = 'primary', className = '', ...props }) {
  return (
    <button
      type="button"
      className={`inline-flex h-10 items-center justify-center gap-2 whitespace-nowrap rounded-full border px-[18px] text-sm font-semibold tracking-[.1px] transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${BTN[variant]} ${className}`}
      {...props}
    />
  )
}

export const inputCls =
  'h-10 w-full rounded-lg border border-outline-variant bg-surface px-3 text-sm text-on-surface placeholder:text-outline focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/25'

export function Field({ label, hint, children, className = '' }) {
  return (
    <label className={`flex flex-col gap-1.5 ${className}`}>
      <span className="text-xs font-semibold tracking-[.5px] text-on-surface-variant">{label}</span>
      {children}
      {hint && <span className="text-xs text-on-surface-variant">{hint}</span>}
    </label>
  )
}

export const ErrorText = ({ children }) =>
  children ? <p role="alert" className="rounded-lg bg-error-container px-3 py-2 text-sm text-on-error-container">{children}</p> : null

const TONES = {
  success: 'bg-success-container text-on-success-container',
  warning: 'bg-warning-container text-on-warning-container',
  error: 'bg-error-container text-on-error-container',
  info: 'bg-tertiary-container text-on-tertiary-container',
  accent: 'bg-accent-container text-on-accent-container',
  primary: 'bg-primary-container text-on-primary-container',
  secondary: 'bg-secondary-container text-on-secondary-container',
  neutral: 'bg-surface-variant text-on-surface-variant',
}

export const Badge = ({ tone = 'neutral', children }) => (
  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold tracking-[.5px] ${TONES[tone]}`}>{children}</span>
)

const STATUS_TONE = {
  ACTIVE: 'success', LIVE: 'success', SCHEDULED: 'info', DRAFT: 'neutral',
  SUSPENDED: 'warning', EXPIRED: 'neutral', CANCELLED: 'error', DEACTIVATED: 'error', INACTIVE: 'neutral',
}
export const StatusBadge = ({ status }) => <Badge tone={STATUS_TONE[status]}>{status[0] + status.slice(1).toLowerCase()}</Badge>

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-display text-[28px] leading-9 font-semibold text-secondary">{title}</h1>
        {subtitle && <p className="mt-1 max-w-[68ch] text-on-surface-variant">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </div>
  )
}

export const Card = ({ className = '', ...p }) => (
  <div className={`rounded-xl border border-outline-variant bg-surface ${className}`} {...p} />
)

/** Filters row above a table. */
export const Toolbar = ({ children }) => <div className="mb-4 flex flex-wrap items-end gap-3">{children}</div>

/** Table shell: horizontal scroll on narrow screens, plus loading / error / empty states. */
export function Table({ head, children, error, loading, empty, colSpan }) {
  const rows = Array.isArray(children) ? children.length : children ? 1 : 0
  return (
    <Card className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            {head.map((h) => (
              <th key={h} className="whitespace-nowrap border-b border-outline-variant bg-surface-variant px-3 py-2.5 text-left text-xs font-semibold text-on-surface-variant">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="[&_td]:border-b [&_td]:border-outline-variant [&_td]:px-3 [&_td]:py-2.5 [&_td]:align-top [&_tr:last-child_td]:border-0">
          {error ? (
            <tr><td colSpan={colSpan ?? head.length} className="text-error">{error}</td></tr>
          ) : loading && !rows ? (
            <tr><td colSpan={colSpan ?? head.length} className="text-on-surface-variant">Loading…</td></tr>
          ) : !rows ? (
            <tr><td colSpan={colSpan ?? head.length} className="py-10! text-center text-on-surface-variant">{empty}</td></tr>
          ) : children}
        </tbody>
      </table>
    </Card>
  )
}

export function Pager({ total, limit, offset, onChange }) {
  if (total <= limit) return null
  return (
    <div className="mt-3 flex items-center justify-end gap-3 text-sm text-on-surface-variant">
      <span>{offset + 1}–{Math.min(offset + limit, total)} of {total}</span>
      <Button variant="outline" className="h-8 px-3" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>Previous</Button>
      <Button variant="outline" className="h-8 px-3" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>Next</Button>
    </div>
  )
}

/** Native <dialog>: focus trap and Esc come free. Mount it to open, unmount to close. */
export function Modal({ title, onClose, children, wide }) {
  const ref = useRef(null)
  useEffect(() => { ref.current.showModal() }, [])
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      className={`m-auto w-[calc(100%-32px)] ${wide ? 'max-w-2xl' : 'max-w-md'} rounded-2xl border border-outline-variant bg-surface p-0 text-on-surface shadow-2xl backdrop:bg-inverse-surface/50`}
    >
      <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
        <h2 className="text-xl leading-7 font-semibold">{title}</h2>
        <button type="button" aria-label="Close" onClick={() => ref.current.close()} className="rounded-full p-1 text-2xl leading-none text-on-surface-variant hover:bg-surface-variant">×</button>
      </div>
      <div className="px-6 py-5">{children}</div>
    </dialog>
  )
}

export const FormActions = ({ busy, label = 'Save', onCancel }) => (
  <div className="mt-2 flex justify-end gap-2">
    <Button variant="text" onClick={onCancel}>Cancel</Button>
    <Button type="submit" disabled={busy}>{busy ? 'Saving…' : label}</Button>
  </div>
)

export function ToastProvider({ children }) {
  const [msg, setMsg] = useState(null)
  useEffect(() => {
    if (!msg) return
    const t = setTimeout(() => setMsg(null), 3500)
    return () => clearTimeout(t)
  }, [msg])
  return (
    <ToastCtx.Provider value={setMsg}>
      {children}
      {msg && (
        <div role="status" className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-inverse-surface px-4 py-3 text-sm text-inverse-on-surface shadow-lg">{msg}</div>
      )}
    </ToastCtx.Provider>
  )
}
