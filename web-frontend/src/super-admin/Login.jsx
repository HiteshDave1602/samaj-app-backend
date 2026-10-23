import { useState } from 'react'
import { api, setToken, useSubmit } from './api'
import { Button, ErrorText, Field, inputCls } from './ui'

// POST /login -> token when the server has MFA off; else (first time) /mfa/enroll -> /mfa/verify -> token. The panel then checks the role.
export default function Login({ onLogin, notice }) {
  const [ticket, setTicket] = useState(null)
  const [enroll, setEnroll] = useState(null) // { secret, otpauth_uri } on first login

  async function start(token) {
    setToken(token)
    const me = await api('/admin/auth/me')
    if (me.role !== 'SUPER_ADMIN') {
      await api('/admin/auth/logout', { method: 'POST' }).catch(() => {})
      setToken(null)
      throw new Error('This panel is for the Super Admin. City Admins use the City Admin panel.')
    }
    onLogin(me)
  }

  const login = useSubmit(async ({ email, password }) => {
    const r = await api('/admin/auth/login', { method: 'POST', body: { email: email.trim(), password } })
    if (r.access_token) return start(r.access_token) // MFA switched off on the server (ADMIN_MFA=false)
    if (!r.mfa_enrolled) setEnroll(await api('/admin/auth/mfa/enroll', { method: 'POST', body: { mfa_ticket: r.mfa_ticket } }))
    setTicket(r.mfa_ticket)
  })

  const verify = useSubmit(async ({ code }) => {
    const r = await api('/admin/auth/mfa/verify', { method: 'POST', body: { mfa_ticket: ticket, code: code.trim() } })
    await start(r.access_token)
  })

  const restart = () => { setTicket(null); setEnroll(null) }

  return (
    <div className="flex min-h-svh items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <Lotus className="mx-auto mb-3 h-12 w-12" />
          <h1 className="font-display text-[32px] leading-10 font-bold text-secondary">Samaj</h1>
          <p className="text-xs font-semibold tracking-[.5px] text-heritage-text uppercase">Super Admin</p>
        </div>

        <div className="rounded-2xl border border-outline-variant bg-surface p-6 shadow-sm">
          {!ticket ? (
            <form onSubmit={login.onSubmit} className="flex flex-col gap-4">
              <h2 className="text-xl leading-7 font-semibold">Sign in</h2>
              {notice && <p className="rounded-lg bg-warning-container px-3 py-2 text-sm text-on-warning-container">{notice}</p>}
              <Field label="Email"><input name="email" type="email" required autoComplete="username" autoFocus className={inputCls} /></Field>
              <Field label="Password"><input name="password" type="password" required autoComplete="current-password" className={inputCls} /></Field>
              <ErrorText>{login.error}</ErrorText>
              <Button type="submit" disabled={login.busy}>{login.busy ? 'Signing in…' : 'Continue'}</Button>
            </form>
          ) : (
            <form onSubmit={verify.onSubmit} className="flex flex-col gap-4">
              <h2 className="text-xl leading-7 font-semibold">{enroll ? 'Set up two-step verification' : 'Two-step verification'}</h2>
              {enroll && (
                <div className="flex flex-col gap-2 text-sm text-on-surface-variant">
                  <p>Add this key to an authenticator app (Google Authenticator, Microsoft Authenticator, Authy), then enter the 6-digit code it shows.</p>
                  <code className="rounded-lg bg-surface-variant px-3 py-2 text-center font-mono text-[15px] font-semibold tracking-wider break-all text-on-surface select-all">
                    {enroll.secret.match(/.{1,4}/g).join(' ')}
                  </code>
                  <a href={enroll.otpauth_uri} className="text-center font-semibold text-primary underline-offset-2 hover:underline">Open in authenticator app</a>
                </div>
              )}
              {!enroll && <p className="text-sm text-on-surface-variant">Enter the 6-digit code from your authenticator app.</p>}
              <Field label="Code">
                <input name="code" required inputMode="numeric" pattern="\d{6}" maxLength={6} autoComplete="one-time-code" autoFocus
                  className={`${inputCls} text-center font-mono text-lg tracking-[.4em]`} />
              </Field>
              <ErrorText>{verify.error}</ErrorText>
              <Button type="submit" disabled={verify.busy}>{verify.busy ? 'Verifying…' : 'Verify'}</Button>
              <Button variant="text" onClick={restart}>Use a different account</Button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}

/** Simple lotus mark in the logo's reference hues. */
export function Lotus({ className }) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden="true">
      <path d="M24 8c5 6 6 14 0 24-6-10-5-18 0-24Z" fill="#E0077D" />
      <path d="M24 32C17 28 10 22 8 14c8 1 14 7 16 18Z" fill="#A3447F" />
      <path d="M24 32c7-4 14-10 16-18-8 1-14 7-16 18Z" fill="#A3447F" />
      <path d="M8 34c6 4 26 4 32 0" stroke="#F08000" strokeWidth="3" fill="none" strokeLinecap="round" />
      <path d="M14 40c4 2 16 2 20 0" stroke="#C08552" strokeWidth="2" fill="none" strokeLinecap="round" />
    </svg>
  )
}
