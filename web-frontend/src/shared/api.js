import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { checkControl, fieldLabel } from './validate'

// sessionStorage: the admin token dies with the tab instead of lingering on a shared machine.
// One key per panel (/super-admin/, /city-admin/) so signing in to one doesn't clobber the other.
// The sign-in page (/) puts the token under the key of the panel it opens.
export const PANEL_PATH = { SUPER_ADMIN: 'super-admin', CITY_ADMIN: 'city-admin' }
const key = (panel = location.pathname.split('/')[1]) => `samaj_token_${panel}`
export const getToken = () => sessionStorage.getItem(key())
export const setToken = (t, panel) => (t ? sessionStorage.setItem(key(panel), t) : sessionStorage.removeItem(key(panel)))

// Why the panel sent the person back to sign in (e.g. session expired); shown once on the sign-in page.
export function toSignIn(notice) {
  if (notice) sessionStorage.setItem('samaj_notice', notice)
  location.assign('/')
}
export function takeNotice() {
  const n = sessionStorage.getItem('samaj_notice')
  sessionStorage.removeItem('samaj_notice')
  return n
}

let onExpired = () => {}
export const setOnExpired = (fn) => { onExpired = fn }

function detail(json, fallback) {
  const fields = json?.error?.fields
  if (fields) return Object.entries(fields).map(([k, m]) => (k === 'body' ? m : `${fieldLabel(k)}: ${m}`)).join('; ')
  const d = json?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((e) => e.msg.replace(/^Value error, /, '')).join('; ')
  return fallback
}

/** fetch with the bearer token; throws Error(message from FastAPI's `detail`). */
export async function api(path, { method = 'GET', body, form, raw } = {}) {
  const token = getToken()
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const res = await fetch(path, { method, headers, body: form ?? (body === undefined ? undefined : JSON.stringify(body)) })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    if (res.status === 401 && token) { setToken(null); onExpired(detail(json, 'Session expired')) }
    // fields: {name: message} from a 422, so useSubmit can mark the inputs themselves
    throw Object.assign(new Error(detail(json, `${res.status} ${res.statusText}`)), { status: res.status, fields: json?.error?.fields })
  }
  if (raw) return res
  return res.status === 204 ? null : res.json()
}

/** Query string from an object, skipping empty values. */
export function qs(params) {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== '' && v != null) p.set(k, v)
  const s = p.toString()
  return s ? `?${s}` : ''
}

/** Fetch a file through api() and save it; the server's filename wins. Returns the Response for its headers. */
export async function download(path, filename, opts) {
  const res = await api(path, { ...opts, raw: true })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(await res.blob())
  a.download = res.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1] ?? filename
  a.click()
  URL.revokeObjectURL(a.href)
  return res
}

/** Object URL for a file behind the bearer token (an <img src> can't send it). '' if it fails to load. */
export function useFileUrl(path) {
  const [url, setUrl] = useState(null)
  useEffect(() => {
    let live = true
    let made
    api(path, { raw: true }).then((r) => r.blob()).then(
      (b) => { made = URL.createObjectURL(b); if (live) setUrl(made); else URL.revokeObjectURL(made) },
      () => live && setUrl(''),
    )
    return () => { live = false; if (made) URL.revokeObjectURL(made) }
  }, [path])
  return url
}

const POLL_MS = 30_000

/** GET `path` whenever it changes (null: don't fetch); reload() refetches. It also refetches every 30 s while the
 * tab is visible and on coming back to the tab, so changes made elsewhere (the app, another admin) show without a
 * page refresh. */
// ponytail: polling, ~12 req/min on the busiest page (limit 300); server push if that ever matters.
export function useLoad(path) {
  const [state, setState] = useState({ data: null, error: null, path: null })
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const visible = () => document.visibilityState === 'visible'
    const onVisible = () => visible() && setTick((t) => t + 1)
    const timer = setInterval(onVisible, POLL_MS)
    document.addEventListener('visibilitychange', onVisible)
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange', onVisible) }
  }, [])
  useEffect(() => {
    if (!path) return
    let live = true
    api(path).then(
      (data) => live && setState({ data, error: null, path }),
      (e) => live && setState((s) => ({ ...s, error: e.message, path })),
    )
    return () => { live = false }
  }, [path, tick])
  return { data: state.data, error: state.error, loading: state.path !== path, reload: () => setTick((t) => t + 1) }
}

// A message set on an input stays until the person edits that input.
const watched = new WeakSet()
function watch(form) {
  if (watched.has(form)) return
  watched.add(form)
  form.addEventListener('input', (e) => e.target.setCustomValidity?.(''))
}

/** Form submit with busy + error state. fn gets the form's fields as an object, plus the FormData for getAll().
 * Every form gets the shared field rules (validate.js) on top of the browser's required/maxLength/type checks, the
 * server's field errors shown on the inputs themselves, and one submission at a time. */
export function useSubmit(fn) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const running = useRef(false) // state lags a render behind; a fast double Enter must not send twice
  async function onSubmit(e) {
    e.preventDefault()
    const form = e.currentTarget
    if (running.current) return
    watch(form)
    for (const el of form.elements) el.setCustomValidity?.(checkControl(el))
    if (!form.reportValidity()) return // the browser shows the first problem on its field
    const fd = new FormData(form)
    running.current = true
    setBusy(true)
    setError(null)
    try {
      await fn(Object.fromEntries(fd), fd)
    } catch (x) {
      setError(x.message)
      const els = Object.entries(x.fields ?? {}).map(([k, m]) => [form.elements.namedItem(k), m]).filter(([el]) => el?.setCustomValidity)
      for (const [el, m] of els) el.setCustomValidity(m)
      if (els.length) form.reportValidity()
    } finally {
      running.current = false
      setBusy(false)
    }
  }
  return { onSubmit, busy, error }
}

export const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)

/**
 * The panel's own confirm() (dialog in ui.jsx, mounted by ToastProvider):
 * `if (!(await confirm({ title, body, action, danger }))) return`. Resolves false on Cancel, Esc or the backdrop.
 */
export const ConfirmCtx = createContext(async () => false)
export const useConfirm = () => useContext(ConfirmCtx)

const dtf = new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
const df = new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' })
export const fmtDateTime = (iso) => (iso ? dtf.format(new Date(iso)) : '—')
export const fmtDate = (iso) => (iso ? df.format(new Date(iso)) : '—')
