import { createContext, useContext, useEffect, useState } from 'react'

// sessionStorage: the admin token dies with the tab instead of lingering on a shared machine.
// One key per panel (/super-admin/, /city-admin/) so signing in to one doesn't clobber the other.
const KEY = `samaj_token_${location.pathname.split('/')[1]}`
export const getToken = () => sessionStorage.getItem(KEY)
export const setToken = (t) => (t ? sessionStorage.setItem(KEY, t) : sessionStorage.removeItem(KEY))

let onExpired = () => {}
export const setOnExpired = (fn) => { onExpired = fn }

function detail(json, fallback) {
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
    throw new Error(detail(json, `${res.status} ${res.statusText}`))
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

/** GET `path` whenever it changes (null: don't fetch); reload() refetches. */
export function useLoad(path) {
  const [state, setState] = useState({ data: null, error: null, path: null })
  const [tick, setTick] = useState(0)
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

/** Form submit with busy + error state. fn gets the form's fields as an object, plus the FormData for getAll(). */
export function useSubmit(fn) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  async function onSubmit(e) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    setBusy(true)
    setError(null)
    try { await fn(Object.fromEntries(fd), fd) } catch (x) { setError(x.message) } finally { setBusy(false) }
  }
  return { onSubmit, busy, error }
}

export const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)

const dtf = new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
const df = new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' })
export const fmtDateTime = (iso) => (iso ? dtf.format(new Date(iso)) : '—')
export const fmtDate = (iso) => (iso ? df.format(new Date(iso)) : '—')
