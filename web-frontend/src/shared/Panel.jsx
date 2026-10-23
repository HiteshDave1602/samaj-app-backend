import { useEffect, useState } from 'react'
import { api, getToken, setOnExpired, setToken } from './api'
import Login, { Lotus } from './Login'
import { ToastProvider } from './ui'

const pageFromHash = (pages) => pages.find((p) => p.id === location.hash.slice(1)) ?? pages[0]

function useTheme() {
  const [theme, setTheme] = useState(() => {
    let saved = null
    try { saved = localStorage.getItem('theme') } catch { /* private mode */ }
    return saved ?? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
  })
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('theme', theme) } catch { /* private mode */ }
  }, [theme])
  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))]
}

/** Sign-in gate + sidebar shell shared by both panels. `role` is the only role allowed in. */
export default function Panel({ role, label, pages }) {
  const [me, setMe] = useState(null)
  const [checking, setChecking] = useState(() => Boolean(getToken()))
  const [notice, setNotice] = useState(null)
  const [page, setPage] = useState(() => pageFromHash(pages))
  const [theme, toggleTheme] = useTheme()

  useEffect(() => {
    setOnExpired((msg) => { setMe(null); setNotice(msg) })
    if (getToken()) api('/admin/auth/me').then((m) => m.role === role && setMe(m)).catch(() => {}).finally(() => setChecking(false))
  }, [role])

  useEffect(() => {
    const onHash = () => setPage(pageFromHash(pages))
    addEventListener('hashchange', onHash)
    return () => removeEventListener('hashchange', onHash)
  }, [pages])

  async function logout() {
    await api('/admin/auth/logout', { method: 'POST' }).catch(() => {})
    setToken(null)
    setMe(null)
    setNotice(null)
  }

  if (checking) return null
  if (!me) return <Login role={role} label={label} notice={notice} onLogin={(m) => { setNotice(null); setMe(m) }} />

  const Page = page.el
  return (
    <ToastProvider>
      <div className="min-h-svh md:grid md:grid-cols-[248px_1fr]">
        <aside className="sticky top-0 z-10 flex flex-col border-b border-outline-variant bg-surface md:h-svh md:border-r md:border-b-0">
          <div className="flex items-center gap-3 px-5 py-4 md:py-6">
            <Lotus className="h-9 w-9 shrink-0" />
            <div className="min-w-0">
              <div className="font-display text-xl leading-6 font-bold text-secondary">Samaj</div>
              <div className="truncate text-[11px] font-semibold tracking-[.5px] text-heritage-text uppercase">{label}{me.city_name && ` · ${me.city_name}`}</div>
            </div>
            <button type="button" onClick={logout} className="ml-auto text-sm font-semibold text-primary md:hidden">Sign out</button>
          </div>
          <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-1 md:flex-col md:overflow-y-auto md:pb-0">
            {pages.map((p) => {
              const active = p.id === page.id
              return (
                <a key={p.id} href={`#${p.id}`} aria-current={active ? 'page' : undefined}
                  className={`flex shrink-0 items-center gap-3 rounded-full px-4 py-2.5 text-sm font-semibold transition-colors ${active ? 'bg-primary-container text-on-primary-container' : 'text-on-surface-variant hover:bg-surface-variant'}`}>
                  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={p.icon} /></svg>
                  {p.label}
                </a>
              )
            })}
          </nav>
          <div className="hidden border-t border-outline-variant p-4 md:block">
            <div className="truncate text-sm font-semibold">{me.full_name}</div>
            <div className="mb-3 truncate text-xs text-on-surface-variant">{me.email}</div>
            <div className="flex gap-2">
              <button type="button" onClick={toggleTheme} className="flex-1 rounded-full border border-outline px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary-container/60">
                {theme === 'dark' ? 'Light mode' : 'Dark mode'}
              </button>
              <button type="button" onClick={logout} className="flex-1 rounded-full border border-outline px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary-container/60">Sign out</button>
            </div>
          </div>
        </aside>
        <main className="mx-auto w-full max-w-[1180px] px-4 py-6 md:px-8 md:py-8">
          <Page me={me} />
        </main>
      </div>
    </ToastProvider>
  )
}
