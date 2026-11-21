import { useEffect, useState } from 'react'
import { api, getToken, setOnExpired, setToken, toSignIn, useLoad, useSubmit } from './api'
import { Lotus } from './Login'
import { Button, Card, ErrorText, Field, PageHeader, ToastProvider, inputCls } from './ui'

const pageFromHash = (pages) => pages.find((p) => p.id === location.hash.slice(1)) ?? pages[0]

const NavLink = ({ p, active }) => (
  <a href={`#${p.id}`} aria-current={active ? 'page' : undefined}
    className={`flex shrink-0 items-center gap-3 rounded-full px-4 py-2.5 text-sm font-semibold transition-colors ${active ? 'bg-primary-container text-on-primary-container' : 'text-on-surface-variant hover:bg-surface-variant'}`}>
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={p.icon} /></svg>
    {p.label}
  </a>
)

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

/** Super Admin in the City Admin panel: pick (or switch) the city to act as City Admin for. */
function ChooseCity({ me, onChosen }) {
  const cities = useLoad('/admin/auth/cities')
  const choose = useSubmit(async ({ city_id }) => {
    await api('/admin/auth/city', { method: 'PUT', body: { city_id } })
    onChosen()
  })
  return (
    <>
      <PageHeader title="Choose a city" subtitle="You are signed in as the Super Admin. Pick the city to manage as its City Admin." />
      <Card className="max-w-md p-5">
        <form onSubmit={choose.onSubmit} className="flex flex-col gap-4">
          <Field label="City">
            <select name="city_id" required defaultValue={me.city_id ?? ''} className={inputCls}>
              <option value="" disabled>{cities.loading ? 'Loading…' : 'Select a city'}</option>
              {cities.data?.map((c) => <option key={c.city_id} value={c.city_id}>{c.name}, {c.state}</option>)}
            </select>
          </Field>
          <ErrorText>{cities.error ?? choose.error}</ErrorText>
          <Button type="submit" disabled={choose.busy} className="self-start">{choose.busy ? 'Opening…' : 'Open'}</Button>
        </form>
      </Card>
    </>
  )
}

/** Session gate + sidebar shell shared by both panels. `role` is the only role allowed in; anyone else goes to the sign-in page (/). */
export default function Panel({ role, label, pages }) {
  const [me, setMe] = useState(null)
  const [choosingCity, setChoosingCity] = useState(false)
  const [page, setPage] = useState(() => pageFromHash(pages))
  const [theme, toggleTheme] = useTheme()

  const loadMe = () => api('/admin/auth/me').then((m) => (m.role === role ? setMe(m) : toSignIn()))

  useEffect(() => {
    setOnExpired(toSignIn)
    if (getToken()) loadMe().catch(() => toSignIn())
    else toSignIn()
  }, [role]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onHash = () => setPage(pageFromHash(pages))
    addEventListener('hashchange', onHash)
    return () => removeEventListener('hashchange', onHash)
  }, [pages])

  async function logout() {
    await api('/admin/auth/logout', { method: 'POST' }).catch(() => {})
    setToken(null)
    toSignIn()
  }

  if (!me) return null

  const Page = page.el
  const actingSuperAdmin = me.is_super_admin && role === 'CITY_ADMIN'
  const profile = pages.find((p) => p.id === 'profile') // lives under the name/email, not in the nav
  return (
    <ToastProvider>
      <div className="min-h-svh md:grid md:grid-cols-[248px_1fr]">
        <aside className="sticky top-0 z-10 flex flex-col border-b border-outline-variant bg-surface md:h-svh md:border-r md:border-b-0">
          <div className="flex items-center gap-3 px-5 py-4 md:py-6">
            <Lotus className="h-9 w-9 shrink-0" />
            <div className="min-w-0">
              <div className="font-display text-xl leading-6 font-bold text-secondary">Samaj</div>
              <div className="truncate text-[11px] font-semibold tracking-[.5px] text-heritage-text uppercase">{label}{me.city_name && ` · ${me.city_name}`}</div>
              {actingSuperAdmin && me.city_id && (
                <button type="button" onClick={() => setChoosingCity(true)} className="text-xs font-semibold text-primary hover:underline">Switch city</button>
              )}
            </div>
            {profile
              ? <a href="#profile" className="ml-auto text-sm font-semibold text-primary md:hidden">Profile</a>
              : <button type="button" onClick={logout} className="ml-auto text-sm font-semibold text-primary md:hidden">Sign out</button>}
          </div>
          <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-1 md:flex-col md:overflow-y-auto md:pb-0">
            {pages.filter((p) => p !== profile).map((p) => <NavLink key={p.id} p={p} active={p.id === page.id} />)}
          </nav>
          <div className="hidden border-t border-outline-variant p-4 md:block">
            <div className="truncate text-sm font-semibold">{me.full_name}</div>
            <div className="mb-3 truncate text-xs text-on-surface-variant">{me.email}</div>
            {profile ? <NavLink p={profile} active={page === profile} /> : (
              <div className="flex gap-2">
                <button type="button" onClick={toggleTheme} className="flex-1 rounded-full border border-outline px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary-container/60">
                  {theme === 'dark' ? 'Light mode' : 'Dark mode'}
                </button>
                <button type="button" onClick={logout} className="flex-1 rounded-full border border-outline px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary-container/60">Sign out</button>
              </div>
            )}
          </div>
        </aside>
        <main className="mx-auto w-full max-w-[1180px] px-4 py-6 md:px-8 md:py-8">
          {actingSuperAdmin && (choosingCity || !me.city_id)
            ? <ChooseCity me={me} onChosen={() => loadMe().then(() => setChoosingCity(false))} />
            // key: a new city remounts the page, so nothing from the previous city stays on screen
            : <Page key={me.city_id} me={me} reloadMe={loadMe} theme={theme} toggleTheme={toggleTheme} logout={logout} />}
        </main>
      </div>
    </ToastProvider>
  )
}
