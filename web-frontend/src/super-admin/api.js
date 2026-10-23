import { createContext, useContext, useEffect, useState } from 'react'

// sessionStorage: the admin token dies with the tab instead of lingering on a shared machine.
const KEY = 'samaj_sa_token'
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

/** GET `path` whenever it changes; reload() refetches. */
export function useLoad(path) {
  const [state, setState] = useState({ data: null, error: null, path: null })
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let live = true
    api(path).then(
      (data) => live && setState({ data, error: null, path }),
      (e) => live && setState((s) => ({ ...s, error: e.message, path })),
    )
    return () => { live = false }
  }, [path, tick])
  return { data: state.data, error: state.error, loading: state.path !== path, reload: () => setTick((t) => t + 1) }
}

/** Form submit with busy + error state. fn gets the form's fields as an object. */
export function useSubmit(fn) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  async function onSubmit(e) {
    e.preventDefault()
    const fields = Object.fromEntries(new FormData(e.currentTarget))
    setBusy(true)
    setError(null)
    try { await fn(fields) } catch (x) { setError(x.message) } finally { setBusy(false) }
  }
  return { onSubmit, busy, error }
}

export const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)

const dtf = new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
const df = new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' })
export const fmtDateTime = (iso) => (iso ? dtf.format(new Date(iso)) : '—')
export const fmtDate = (iso) => (iso ? df.format(new Date(iso)) : '—')
