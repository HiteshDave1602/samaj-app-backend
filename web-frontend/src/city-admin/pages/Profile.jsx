import { useState } from 'react'
import { api, fmtDate, useSubmit, useToast } from '../../shared/api'
import { Button, Card, Detail, ErrorText, Field, PageHeader, inputCls } from '../../shared/ui'

const Section = ({ title, children }) => (
  <Card className="p-5">
    <h2 className="mb-4 text-lg leading-6 font-semibold">{title}</h2>
    {children}
  </Card>
)

const PasswordFields = ({ current }) => (
  <>
    <Field label={current}>
      <input name="current_password" type="password" required autoComplete="current-password" className={inputCls} />
    </Field>
    <Field label="New password" hint="At least 12 characters.">
      <input name="new_password" type="password" required minLength={12} maxLength={128} autoComplete="new-password" className={inputCls} />
    </Field>
    <Field label="Confirm new password">
      <input name="confirm_password" type="password" required minLength={12} maxLength={128} autoComplete="new-password" className={inputCls} />
    </Field>
  </>
)

/** `key` changes after a save, so the form remounts empty. */
function usePasswordForm(path, done) {
  const [key, setKey] = useState(0)
  const submit = useSubmit(async ({ current_password, new_password, confirm_password }) => {
    if (new_password !== confirm_password) throw new Error('New passwords do not match')
    await api(path, { method: 'POST', body: { current_password, new_password } })
    setKey((k) => k + 1)
    done()
  })
  return { ...submit, key }
}

/** Both panels. reloadMe / theme / toggleTheme / logout come from Panel, which owns them. */
export default function Profile({ me, reloadMe, theme, toggleTheme, logout }) {
  const toast = useToast()
  const dark = theme === 'dark'
  const superPanel = me.role === 'SUPER_ADMIN'
  const roleLabel = !me.is_super_admin ? 'City Admin' : superPanel ? 'Super Admin' : 'Super Admin, acting as City Admin'
  const hasCityPw = me.has_city_panel_password

  const pw = usePasswordForm('/admin/auth/change-password', () => toast('Password changed. Other devices have been signed out.'))
  const cityPw = usePasswordForm('/admin/auth/city-panel-password', () => {
    reloadMe() // Panel's `me` is what every page sees; keep it current, not a copy here
    toast('City Admin panel password saved. City Admin panel sessions have been signed out.')
  })

  return (
    <>
      <PageHeader title="Profile" subtitle="Your sign-in details and panel settings." />
      <div className="grid max-w-3xl gap-4">
        <Section title="Login credentials">
          <dl className="grid gap-4 text-sm sm:grid-cols-2">
            <Detail label="Name">{me.full_name}</Detail>
            <Detail label="Email (sign-in ID)"><span className="break-all">{me.email}</span></Detail>
            <Detail label="Role">{roleLabel}</Detail>
            {!superPanel && <Detail label="City">{me.city_name ?? '—'}</Detail>}
            <Detail label="Password">••••••••••••</Detail>
            <Detail label="Two-step verification">{me.mfa_enrolled_at ? `On since ${fmtDate(me.mfa_enrolled_at)}` : 'Not set up'}</Detail>
          </dl>
          {!me.is_super_admin && <p className="mt-4 text-xs text-on-surface-variant">To change your name or email, or to reset two-step verification, ask the Super Admin.</p>}
        </Section>

        <Section title={superPanel || !me.is_super_admin ? 'Reset password' : 'Reset City Admin panel password'}>
          <form key={pw.key} onSubmit={pw.onSubmit} className="flex flex-col gap-4 sm:max-w-sm">
            <PasswordFields current="Current password" />
            <ErrorText>{pw.error}</ErrorText>
            <p className="text-xs text-on-surface-variant">You stay signed in here; every other device is signed out.</p>
            <Button type="submit" disabled={pw.busy} className="self-start">{pw.busy ? 'Saving…' : 'Change password'}</Button>
          </form>
        </Section>

        {superPanel && (
          <Section title="City Admin panel password">
            <form key={cityPw.key} onSubmit={cityPw.onSubmit} className="flex flex-col gap-4 sm:max-w-sm">
              <p className="text-sm text-on-surface-variant">
                Sign in with your email and this password to open the City Admin panel for any city.
                It must be different from your Super Admin password. {hasCityPw ? 'One is set; saving replaces it.' : 'Not set yet.'}
              </p>
              <PasswordFields current="Super Admin password" />
              <ErrorText>{cityPw.error}</ErrorText>
              <Button type="submit" disabled={cityPw.busy} className="self-start">{cityPw.busy ? 'Saving…' : hasCityPw ? 'Replace' : 'Set password'}</Button>
            </form>
          </Section>
        )}

        <Section title="Appearance">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div id="dark-mode-label" className="text-sm font-semibold">Dark mode</div>
              <div className="text-xs text-on-surface-variant">Saved in this browser.</div>
            </div>
            <button type="button" role="switch" aria-checked={dark} aria-labelledby="dark-mode-label" onClick={toggleTheme}
              className={`relative h-6 w-11 shrink-0 rounded-full transition-colors focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:outline-none ${dark ? 'bg-primary' : 'bg-outline'}`}>
              <span className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-surface shadow transition-transform ${dark ? 'translate-x-5' : ''}`} />
            </button>
          </div>
        </Section>

        <Section title="Sign out">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="text-sm text-on-surface-variant">End your session on this device.</p>
            <Button variant="outline" onClick={logout}>Sign out</Button>
          </div>
        </Section>
      </div>
    </>
  )
}
