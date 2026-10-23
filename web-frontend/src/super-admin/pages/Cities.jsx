import { useState } from 'react'
import { api, fmtDate, qs, useLoad, useSubmit, useToast } from '../api'
import { Button, ErrorText, Field, FormActions, Modal, PageHeader, StatusBadge, Table, Toolbar, inputCls } from '../ui'

export default function Cities() {
  const [active, setActive] = useState('')
  const [editing, setEditing] = useState(null) // {} for new, a city to edit
  const [error, setError] = useState(null)
  const list = useLoad(`/superadmin/cities${qs({ is_active: active })}`)
  const toast = useToast()

  async function toggle(c) {
    setError(null)
    try {
      await api(`/superadmin/cities/${c.city_id}`, { method: 'PUT', body: { is_active: !c.is_active } })
      toast(`${c.name} ${c.is_active ? 'deactivated' : 'activated'}`)
      list.reload()
    } catch (e) { setError(e.message) }
  }

  return (
    <>
      <PageHeader title="Cities" subtitle="Cities can't be deleted once members or admins use them. Deactivate a city to hide it from new registrations.">
        <Button onClick={() => setEditing({})}>Add city</Button>
      </PageHeader>
      <Toolbar>
        <Field label="Status">
          <select value={active} onChange={(e) => setActive(e.target.value)} className={inputCls}>
            <option value="">All</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </Field>
      </Toolbar>
      <div className="mb-3"><ErrorText>{error}</ErrorText></div>
      <Table head={['City', 'State', 'Status', 'Added', '']} error={list.error} loading={list.loading} empty="No cities yet. Add the first one.">
        {list.data?.map((c) => (
          <tr key={c.city_id}>
            <td className="font-semibold">{c.name}</td>
            <td>{c.state}</td>
            <td><StatusBadge status={c.is_active ? 'ACTIVE' : 'INACTIVE'} /></td>
            <td className="whitespace-nowrap">{fmtDate(c.created_at)}</td>
            <td className="text-right whitespace-nowrap">
              <Button variant="text" className="h-8 px-3" onClick={() => setEditing(c)}>Edit</Button>
              <Button variant="text" className="h-8 px-3" onClick={() => toggle(c)}>{c.is_active ? 'Deactivate' : 'Activate'}</Button>
            </td>
          </tr>
        ))}
      </Table>
      {editing && <CityForm city={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); list.reload() }} />}
    </>
  )
}

function CityForm({ city, onClose, onSaved }) {
  const toast = useToast()
  const { onSubmit, busy, error } = useSubmit(async (f) => {
    if (city.city_id) await api(`/superadmin/cities/${city.city_id}`, { method: 'PUT', body: f })
    else await api('/superadmin/cities', { method: 'POST', body: f })
    toast(city.city_id ? 'City updated' : `${f.name} added`)
    onSaved()
  })
  return (
    <Modal title={city.city_id ? 'Edit city' : 'Add city'} onClose={onClose}>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <Field label="City name"><input name="name" required maxLength={80} defaultValue={city.name} autoFocus className={inputCls} /></Field>
        <Field label="State"><input name="state" required maxLength={60} defaultValue={city.state} placeholder="e.g. Gujarat" className={inputCls} /></Field>
        <ErrorText>{error}</ErrorText>
        <FormActions busy={busy} label={city.city_id ? 'Save' : 'Add city'} onCancel={onClose} />
      </form>
    </Modal>
  )
}
