import { useState } from 'react'
import { api, fmtDate, fmtDateTime, qs, useFileUrl, useLoad, useToast } from '../../shared/api'
import { Badge, Button, Detail, ErrorText, Field, Modal, PageHeader, Pager, Stat, StatusBadge, Table, Toolbar, inputCls } from '../../shared/ui'
import Decide from '../Decide'
import { Waiting } from './Dashboard'

const LIMIT = 50

// Both panels. The Super Admin sees every city (or one) read-only; approving stays with each City Admin.
export default function Members({ me }) {
  const sa = me.role === 'SUPER_ADMIN'
  const base = sa ? '/superadmin/members' : '/cityadmin/members'
  const [cityId, setCityId] = useState('')
  const [status, setStatus] = useState('PENDING')
  const [q, setQ] = useState('')
  const [offset, setOffset] = useState(0)
  const [picked, setPicked] = useState(new Set())
  const [open, setOpen] = useState(null) // member_id under review
  const [error, setError] = useState(null)
  const toast = useToast()
  const query = q.trim()
  const cities = useLoad(sa ? '/superadmin/cities' : null)
  const cityName = Object.fromEntries(cities.data?.map((c) => [c.city_id, c.name]) ?? [])
  // 'none': registrations for a city that isn't set up yet; the Super Admin decides those (no City Admin exists)
  const scope = cityId === 'none' ? { no_city: true } : { city_id: cityId }
  const counts = useLoad(sa ? `${base}/counts${qs({ city_id: cityId === 'none' ? '' : cityId })}` : null)
  const n = (s) => counts.data && (counts.data[s] ?? 0)
  // The pending queue is oldest first (the 72 h clock); everything else, and any search, is by name.
  const path = status === 'PENDING' && !query
    ? `${base}/pending${qs({ ...scope, limit: LIMIT, offset })}`
    : `${base}${qs({ status, q: query, ...scope, limit: LIMIT, offset })}`
  const list = useLoad(path)
  const items = list.data?.items ?? []
  const pendingIds = sa ? [] : items.filter((m) => m.status === 'PENDING').map((m) => m.member_id)

  const refilter = (fn) => (e) => { fn(e.target.value); setOffset(0); setPicked(new Set()) }
  const toggle = (id) => setPicked((s) => { const n = new Set(s); if (!n.delete(id)) n.add(id); return n })

  async function bulkApprove() {
    if (!confirm(`Approve ${picked.size} member${picked.size === 1 ? '' : 's'}? Only do this after checking their ID documents.`)) return
    setError(null)
    try {
      const r = await api('/cityadmin/members/bulk-approve', { method: 'POST', body: { member_ids: [...picked] } })
      toast(`${r.approved} approved`)
      setPicked(new Set())
      list.reload()
    } catch (e) { setError(e.message) }
  }

  return (
    <>
      <PageHeader title="Members" subtitle={sa
        ? "Every city's members and their profiles. Each city's City Admin approves or rejects registrations; you decide those for a new city that isn't set up yet."
        : 'Approve new registrations after checking the ID document. Rejected members see your reason in the app.'}>
        {picked.size > 0 && <Button onClick={bulkApprove}>Approve {picked.size} selected</Button>}
      </PageHeader>
      {sa && (
        <div className="mb-6 grid gap-3 sm:grid-cols-3">
          <Stat label="Pending approval" value={n('PENDING')} tone="text-warning" />
          <Stat label="Approved (active)" value={n('ACTIVE')} tone="text-success" />
          <Stat label="Rejected" value={n('REJECTED')} tone="text-error" />
        </div>
      )}
      <Toolbar>
        {sa && (
          <Field label="City">
            <select value={cityId} onChange={refilter(setCityId)} className={inputCls}>
              <option value="">All cities</option>
              <option value="none">New city requested (not set up)</option>
              {cities.data?.map((c) => <option key={c.city_id} value={c.city_id}>{c.name}</option>)}
            </select>
          </Field>
        )}
        <Field label="Status">
          <select value={status} onChange={refilter(setStatus)} className={inputCls}>
            <option value="PENDING">Pending approval</option>
            <option value="ACTIVE">Active</option>
            <option value="REJECTED">Rejected</option>
            <option value="ARCHIVED">Archived</option>
            <option value="">All</option>
          </select>
        </Field>
        <Field label="Search">
          <input type="search" value={q} onChange={refilter(setQ)} placeholder="Name or family name" maxLength={120} className={inputCls} />
        </Field>
        {pendingIds.length > 0 && (
          <Button variant="text" onClick={() => setPicked(picked.size === pendingIds.length ? new Set() : new Set(pendingIds))}>
            {picked.size === pendingIds.length ? 'Clear selection' : 'Select all pending'}
          </Button>
        )}
      </Toolbar>
      <div className="mb-3"><ErrorText>{error}</ErrorText></div>
      <Table head={[...(sa ? [] : ['']), 'Member', ...(sa ? ['City'] : []), 'Family', 'Mobile', 'Status', 'Registered', '']} error={list.error} loading={list.loading}
        empty={status === 'PENDING' && !query ? 'No registrations waiting.' : 'No members match.'}>
        {items.map((m) => (
          <tr key={m.member_id}>
            {!sa && (
              <td className="w-8">
                {m.status === 'PENDING' && (
                  <input type="checkbox" checked={picked.has(m.member_id)} onChange={() => toggle(m.member_id)}
                    aria-label={`Select ${m.full_name ?? 'member'}`} className="h-4 w-4 accent-primary" />
                )}
              </td>
            )}
            <td>
              <div className="font-semibold">{m.full_name ?? <span className="font-normal text-on-surface-variant italic">No name yet</span>}</div>
              <div className="text-xs text-on-surface-variant">{[gender(m.gender), m.dob && fmtDate(m.dob)].filter(Boolean).join(' · ')}</div>
            </td>
            {sa && (
              <td>
                {m.city_id ? cityName[m.city_id] ?? '…' : (
                  <><div>{m.requested_city}</div><Badge tone="warning">New city</Badge></>
                )}
              </td>
            )}
            <td>
              <div>{m.family_name ?? '—'}</div>
              {m.native_place && <div className="text-xs text-on-surface-variant">{m.native_place}</div>}
            </td>
            <td className="font-mono text-xs whitespace-nowrap">{m.mobile_last4 ? `•••• ${m.mobile_last4}` : '—'}</td>
            <td><StatusBadge status={m.status} /></td>
            <td className="whitespace-nowrap">
              {fmtDate(m.created_at)}
              {m.status === 'PENDING' && <div className="mt-1"><Waiting since={m.created_at} /></div>}
            </td>
            <td className="text-right">
              <Button variant="text" className="h-8 px-3" onClick={() => setOpen(m.member_id)}>{m.status === 'PENDING' && (!sa || !m.city_id) ? 'Review' : 'View'}</Button>
            </td>
          </tr>
        ))}
      </Table>
      {list.data && <Pager total={list.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />}
      {open && <Review id={open} base={base} readOnly={sa} onClose={() => { setOpen(null); list.reload(); counts.reload() }} />}
    </>
  )
}

const gender = (g) => g && g[0] + g.slice(1).toLowerCase()

function Review({ id, base, readOnly, onClose }) {
  const m = useLoad(`${base}/${id}`)
  const toast = useToast()

  async function decide(action, body) {
    await api(`${base}/${id}/${action}`, { method: 'POST', body })
    toast(action === 'approve' ? `${m.data.full_name ?? 'Member'} approved` : 'Rejected. The member sees your reason.')
    onClose()
  }

  const d = m.data
  return (
    <Modal title="Member" onClose={onClose} wide>
      {m.error ? <ErrorText>{m.error}</ErrorText> : !d ? <p className="text-on-surface-variant">Loading…</p> : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="font-display text-2xl font-semibold text-secondary">{d.full_name ?? 'No name yet'}</h3>
            <StatusBadge status={d.status} />
          </div>
          <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
            {readOnly && <Detail label="City">{d.city_id ? d.city_name : `${d.requested_city}, ${d.requested_state} (not set up yet)`}</Detail>}
            <Detail label="Mobile">{d.mobile ? <a href={`tel:${d.mobile}`} className="font-mono text-primary">{d.mobile}</a> : '—'}</Detail>
            <Detail label="Gender">{gender(d.gender) ?? '—'}</Detail>
            <Detail label="Date of birth">{d.dob ? fmtDate(d.dob) : '—'}</Detail>
            <Detail label="Family name">{d.family_name ?? '—'}{d.is_household_head && ' (head of household)'}</Detail>
            <Detail label="Native place">{d.native_place ?? '—'}</Detail>
            <Detail label="Registered">{fmtDateTime(d.created_at)}</Detail>
            <Detail label="Address" wide>{d.address ?? '—'}</Detail>
            {d.rejection_reason && <Detail label="Rejection reason" wide>{d.rejection_reason}</Detail>}
            {d.reviewed_at && <Detail label="Reviewed">{fmtDateTime(d.reviewed_at)}</Detail>}
          </dl>
          <div>
            <h4 className="mb-2 text-xs font-semibold tracking-[.5px] text-on-surface-variant uppercase">ID document</h4>
            {d.id_document ? <IdDocument path={`${base}/${id}/id-document`} doc={d.id_document} /> : <p className="text-sm text-on-surface-variant">No ID document uploaded.</p>}
          </div>
          {d.status === 'PENDING' && !readOnly && (
            <Decide onApprove={() => decide('approve')} onReject={(reason) => decide('reject', { reason })} approveLabel="Approve member" />
          )}
          {d.status === 'PENDING' && readOnly && !d.city_id && (
            <NewCityDecide member={d} onApprove={(city_id) => decide('approve', { city_id })} onReject={(reason) => decide('reject', { reason })} />
          )}
        </div>
      )}
    </Modal>
  )
}

/** Super Admin only: the member typed a city that isn't set up, so nobody else can approve. Create the city
 * (or pick one, e.g. a spelling variant), then approve into it. */
function NewCityDecide({ member, onApprove, onReject }) {
  const cities = useLoad('/superadmin/cities?is_active=true')
  const toast = useToast()
  const same = (c) => c.name.toLowerCase() === member.requested_city.toLowerCase()
    && c.state.toLowerCase() === member.requested_state.toLowerCase()
  const [cityId, setCityId] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const match = cities.data?.find(same)
  const picked = cityId || match?.city_id || ''

  async function create() {
    setError(null)
    setBusy(true)
    try {
      const c = await api('/superadmin/cities', { method: 'POST', body: { name: member.requested_city, state: member.requested_state } })
      toast(`${c.name} added`)
      setCityId(c.city_id)
      cities.reload()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-outline-variant p-4">
      <p className="text-sm">
        Registered for <b>{member.requested_city}, {member.requested_state}</b>, a city that isn't set up yet, so it has no City Admin.
        {!match && ' Create the city, or pick an existing one if it is spelled differently, then approve.'}
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <Field label="City">
          <select value={picked} onChange={(e) => setCityId(e.target.value)} className={inputCls}>
            <option value="">Choose a city…</option>
            {cities.data?.map((c) => <option key={c.city_id} value={c.city_id}>{c.name}, {c.state}</option>)}
          </select>
        </Field>
        {!match && (
          <Button variant="outline" onClick={create} disabled={busy}>
            {busy ? 'Creating…' : `Create “${member.requested_city}, ${member.requested_state}”`}
          </Button>
        )}
      </div>
      <ErrorText>{error}</ErrorText>
      <Decide onApprove={() => {
        if (!picked) throw new Error('Choose or create the city first')
        return onApprove(picked)
      }} onReject={onReject} approveLabel="Approve into this city" />
    </div>
  )
}

function IdDocument({ path, doc }) {
  const url = useFileUrl(path)
  if (url === null) return <p className="text-sm text-on-surface-variant">Loading…</p>
  if (!url) return <ErrorText>The ID document couldn't be loaded.</ErrorText>
  if (doc.mime_type === 'application/pdf') return <a href={url} target="_blank" rel="noreferrer" className="font-semibold text-primary underline-offset-2 hover:underline">Open the PDF</a>
  return (
    <a href={url} target="_blank" rel="noreferrer">
      <img src={url} alt="Member's ID document" className="max-h-80 rounded-lg border border-outline-variant object-contain" />
    </a>
  )
}
