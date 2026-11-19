import { useRef } from 'react'
import { api, fmtDate, useSubmit, useToast } from '../../shared/api'
import { Button, Card, Detail, ErrorText, Field, PageHeader, inputCls } from '../../shared/ui'

const Section = ({ title, children }) => (
  <Card className="p-5">
    <h2 className="mb-4 text-lg leading-6 font-semibold">{title}</h2>
    {children}
  </Card>
)

/** theme / toggleTheme / logout come from Panel, which owns them. */
export default function Profile({ me, theme, toggleTheme, logout }) {
  const toast = useToast()
  const form = useRef(null)
  const dark = theme === 'dark'

  const pw = useSubmit(async ({ current_password, new_password, confirm_password }) => {
    if (new_password !== confirm_password) throw new Error('New passwords do not match')
    await api('/admin/auth/change-password', { method: 'POST', body: { current_password, new_password } })
    form.current.reset()
    toast('Password changed. Other devices have been signed out.')
  })

  return (
    <>
      <PageHeader title="Profile" subtitle="Your sign-in details and panel settings." />
      <div className="grid max-w-3xl gap-4">
        <Section title="Login credentials">
          <dl className="grid gap-4 text-sm sm:grid-cols-2">
            <Detail label="Name">{me.full_name}</Detail>
            <Detail label="Email (sign-in ID)"><span className="break-all">{me.email}</span></Detail>
            <Detail label="Role">City Admin</Detail>
            <Detail label="City">{me.city_name ?? '—'}</Detail>
            <Detail label="Password">••••••••••••</Detail>
            <Detail label="Two-step verification">{me.mfa_enrolled_at ? `On since ${fmtDate(me.mfa_enrolled_at)}` : 'Not set up'}</Detail>
          </dl>
          <p className="mt-4 text-xs text-on-surface-variant">To change your name or email, or to reset two-step verification, ask the Super Admin.</p>
        </Section>

        <Section title="Reset password">
          <form ref={form} onSubmit={pw.onSubmit} className="flex flex-col gap-4 sm:max-w-sm">
            <Field label="Current password">
              <input name="current_password" type="password" required autoComplete="current-password" className={inputCls} />
            </Field>
            <Field label="New password" hint="At least 12 characters.">
              <input name="new_password" type="password" required minLength={12} maxLength={128} autoComplete="new-password" className={inputCls} />
            </Field>
            <Field label="Confirm new password">
              <input name="confirm_password" type="password" required minLength={12} maxLength={128} autoComplete="new-password" className={inputCls} />
            </Field>
            <ErrorText>{pw.error}</ErrorText>
            <p className="text-xs text-on-surface-variant">You stay signed in here; every other device is signed out.</p>
            <Button type="submit" disabled={pw.busy} className="self-start">{pw.busy ? 'Saving…' : 'Change password'}</Button>
          </form>
        </Section>

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
