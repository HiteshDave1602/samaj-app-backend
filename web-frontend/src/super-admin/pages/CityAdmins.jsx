import { useState } from 'react'
import { api, fmtDate, fmtDateTime, qs, useLoad, useSubmit, useToast } from '../../shared/api'
import { Badge, Button, ErrorText, Field, FormActions, Modal, PageHeader, StatusBadge, Table, Toolbar, inputCls } from '../../shared/ui'

export default function CityAdmins() {
  const [filters, setFilters] = useState({ city_id: '', status: '' })
  const [modal, setModal] = useState(null) // { kind: 'new' | 'edit' | 'password' | 'mfa', admin }
  const cities = useLoad('/superadmin/cities')
  const list = useLoad(`/superadmin/city-admins${qs(filters)}`)
  const cityName = Object.fromEntries(cities.data?.map((c) => [c.city_id, c.name]) ?? [])
  const close = () => setModal(null)
  const saved = () => { setModal(null); list.reload() }
  const set = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }))

  return (
    <>
      <PageHeader title="City Admins" subtitle="One active admin per city. Suspending, deactivating or resetting credentials signs the admin out everywhere.">
        <Button onClick={() => setModal({ kind: 'new' })}>Add City Admin</Button>
      </PageHeader>
      <Toolbar>
        <Field label="City">
          <select value={filters.city_id} onChange={set('city_id')} className={inputCls}>
            <option value="">All cities</option>
            {cities.data?.map((c) => <option key={c.city_id} value={c.city_id}>{c.name}</option>)}
          </select>
        </Field>
        <Field label="Status">
          <select value={filters.status} onChange={set('status')} className={inputCls}>
            <option value="">All</option>
            <option value="ACTIVE">Active</option>
            <option value="SUSPENDED">Suspended</option>
            <option value="DEACTIVATED">Deactivated</option>
          </select>
        </Field>
      </Toolbar>
      <Table head={['Admin', 'City', 'Status', 'Two-step', 'Last sign-in', '']} error={list.error} loading={list.loading} empty="No City Admins match.">
        {list.data?.map((a) => (
          <tr key={a.admin_id}>
            <td>
              <div className="font-semibold">{a.full_name}</div>
              <div className="text-xs text-on-surface-variant">{a.email}</div>
            </td>
            <td>{cityName[a.city_id] ?? '…'}</td>
            <td><StatusBadge status={a.status} /></td>
            <td>{a.mfa_enrolled_at ? <span title={fmtDateTime(a.mfa_enrolled_at)}>Set up {fmtDate(a.mfa_enrolled_at)}</span> : <Badge tone="accent">Pending</Badge>}</td>
            <td className="whitespace-nowrap">{a.last_login_at ? fmtDateTime(a.last_login_at) : 'Never'}</td>
            <td className="text-right whitespace-nowrap">
              {a.status !== 'DEACTIVATED' && (
                <>
                  <Button variant="text" className="h-8 px-3" onClick={() => setModal({ kind: 'edit', admin: a })}>Edit</Button>
                  <Button variant="text" className="h-8 px-3" onClick={() => setModal({ kind: 'password', admin: a })}>Reset password</Button>
                  {a.mfa_enrolled_at && <Button variant="text" className="h-8 px-3" onClick={() => setModal({ kind: 'mfa', admin: a })}>Reset two-step</Button>}
                </>
              )}
            </td>
          </tr>
        ))}
      </Table>

      {modal?.kind === 'new' && <NewAdmin cities={cities.data?.filter((c) => c.is_active) ?? []} onClose={close} onSaved={saved} />}
      {modal?.kind === 'edit' && <EditAdmin admin={modal.admin} onClose={close} onSaved={saved} />}
      {modal?.kind === 'password' && <ResetPassword admin={modal.admin} onClose={close} onSaved={saved} />}
      {modal?.kind === 'mfa' && <ResetMfa admin={modal.admin} onClose={close} onSaved={saved} />}
    </>
  )
}

const Password = ({ label = 'Password' }) => (
  <Field label={label} hint="At least 12 characters. Share it with the admin privately.">
    <input name="password" type="password" required minLength={12} maxLength={128} autoComplete="new-password" className={inputCls} />
  </Field>
)

function NewAdmin({ cities, onClose, onSaved }) {
  const toast = useToast()
  const { onSubmit, busy, error } = useSubmit(async (f) => {
    await api('/superadmin/city-admins', { method: 'POST', body: { ...f, email: f.email.trim() } })
    toast(`${f.full_name} added. They set up two-step verification on first sign-in.`)
    onSaved()
  })
  return (
    <Modal title="Add City Admin" onClose={onClose}>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <Field label="City">
          <select name="city_id" required className={inputCls} defaultValue="">
            <option value="" disabled>Choose a city</option>
            {cities.map((c) => <option key={c.city_id} value={c.city_id}>{c.name}, {c.state}</option>)}
          </select>
        </Field>
        <Field label="Full name"><input name="full_name" required maxLength={120} className={inputCls} /></Field>
        <Field label="Email"><input name="email" type="email" required maxLength={254} autoComplete="off" className={inputCls} /></Field>
        <Password />
        <ErrorText>{error}</ErrorText>
        <FormActions busy={busy} label="Add admin" onCancel={onClose} />
      </form>
    </Modal>
  )
}

function EditAdmin({ admin, onClose, onSaved }) {
  const toast = useToast()
  const { onSubmit, busy, error } = useSubmit(async (f) => {
    if (f.status === 'DEACTIVATED' && admin.status !== 'DEACTIVATED' &&
      !confirm(`Deactivate ${admin.full_name}? This is permanent; you'd add a new City Admin instead.`)) return
    await api(`/superadmin/city-admins/${admin.admin_id}`, { method: 'PUT', body: { ...f, email: f.email.trim() } })
    toast('City Admin updated')
    onSaved()
  })
  return (
    <Modal title="Edit City Admin" onClose={onClose}>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <Field label="Full name"><input name="full_name" required maxLength={120} defaultValue={admin.full_name} className={inputCls} /></Field>
        <Field label="Email"><input name="email" type="email" required maxLength={254} defaultValue={admin.email} className={inputCls} /></Field>
        <Field label="Status" hint="Suspended admins can be reactivated. Deactivation is final.">
          <select name="status" defaultValue={admin.status} className={inputCls}>
            <option value="ACTIVE">Active</option>
            <option value="SUSPENDED">Suspended</option>
            <option value="DEACTIVATED">Deactivated</option>
          </select>
        </Field>
        <ErrorText>{error}</ErrorText>
        <FormActions busy={busy} onCancel={onClose} />
      </form>
    </Modal>
  )
}

function ResetPassword({ admin, onClose, onSaved }) {
  const toast = useToast()
  const { onSubmit, busy, error } = useSubmit(async ({ password }) => {
    await api(`/superadmin/city-admins/${admin.admin_id}/reset-password`, { method: 'POST', body: { new_password: password } })
    toast(`Password reset for ${admin.full_name}`)
    onSaved()
  })
  return (
    <Modal title="Reset password" onClose={onClose}>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <p className="text-on-surface-variant">Set a new password for <b className="text-on-surface">{admin.full_name}</b>. They'll be signed out of every device.</p>
        <Password label="New password" />
        <ErrorText>{error}</ErrorText>
        <FormActions busy={busy} label="Reset password" onCancel={onClose} />
      </form>
    </Modal>
  )
}

function ResetMfa({ admin, onClose, onSaved }) {
  const toast = useToast()
  const { onSubmit, busy, error } = useSubmit(async () => {
    await api(`/superadmin/city-admins/${admin.admin_id}/reset-mfa`, { method: 'POST' })
    toast(`Two-step verification reset for ${admin.full_name}`)
    onSaved()
  })
  return (
    <Modal title="Reset two-step verification" onClose={onClose}>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <p className="text-on-surface-variant">Use this when <b className="text-on-surface">{admin.full_name}</b> has lost their authenticator. They'll be signed out and set up a new authenticator on their next sign-in.</p>
        <ErrorText>{error}</ErrorText>
        <div className="flex justify-end gap-2">
          <Button variant="text" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="danger" disabled={busy}>{busy ? 'Resetting…' : 'Reset two-step'}</Button>
        </div>
      </form>
    </Modal>
  )
}
