import { useState } from 'react'
import { api, fmtDate, fmtDateTime, qs, useFileUrl, useLoad, useToast } from '../../shared/api'
import { Button, Detail, ErrorText, Field, Modal, PageHeader, Pager, Stat, StatusBadge, Table, Toolbar, inputCls } from '../../shared/ui'
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
  const counts = useLoad(sa ? `${base}/counts${qs({ city_id: cityId })}` : null)
  const n = (s) => counts.data && (counts.data[s] ?? 0)
  // The pending queue is oldest first (the 72 h clock); everything else, and any search, is by name.
  const path = status === 'PENDING' && !query
    ? `${base}/pending${qs({ city_id: cityId, limit: LIMIT, offset })}`
    : `${base}${qs({ status, q: query, city_id: cityId, limit: LIMIT, offset })}`
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
        ? "Every city's members and their profiles. Each city's City Admin approves or rejects registrations."
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
            {sa && <td>{cityName[m.city_id] ?? '…'}</td>}
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
              <Button variant="text" className="h-8 px-3" onClick={() => setOpen(m.member_id)}>{m.status === 'PENDING' && !sa ? 'Review' : 'View'}</Button>
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
            {readOnly && <Detail label="City">{d.city_name}</Detail>}
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
        </div>
      )}
    </Modal>
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
