import { useState } from 'react'
import { api, fmtDate, fmtDateTime, qs, useLoad, useToast } from '../../shared/api'
import { Card, ErrorText, Field, PageHeader, Pager, StatusBadge, Table, Toolbar, inputCls } from '../../shared/ui'
import Decide from '../Decide'

const LIMIT = 50
const LOG_LIMIT = 20
const title = (s) => s && s[0] + s.slice(1).toLowerCase().replaceAll('_', ' ')

export default function FamilyAdditions() {
  const [status, setStatus] = useState('PENDING')
  const [offset, setOffset] = useState(0)
  const [logOffset, setLogOffset] = useState(0)
  const list = useLoad(`/cityadmin/family-additions${qs({ status, limit: LIMIT, offset })}`)
  const log = useLoad(`/cityadmin/family-additions${qs({ status: 'DECIDED', limit: LOG_LIMIT, offset: logOffset })}`)
  const toast = useToast()

  async function decide(r, action, body) {
    await api(`/cityadmin/family-additions/${r.family_member_id}/${action}`, { method: 'POST', body })
    toast(`${r.full_name} ${action === 'approve' ? 'added to the family' : 'rejected'}`)
    list.reload()
    log.reload()
  }

  return (
    <>
      <PageHeader title="Family additions" subtitle="Members asking to add relatives to their household. Approved relatives appear in the family tree and directory." />
      <Toolbar>
        <Field label="Status">
          <select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0) }} className={inputCls}>
            <option value="PENDING">Pending</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
          </select>
        </Field>
      </Toolbar>
      <Table head={['Relative', 'Household', 'Requested by', 'Status', '']} error={list.error} loading={list.loading}
        empty={status === 'PENDING' ? 'No requests waiting.' : 'Nothing here yet.'}>
        {list.data?.items.map((r) => (
          <tr key={r.family_member_id}>
            <td>
              <div className="font-semibold">{r.full_name}</div>
              <div className="text-xs text-on-surface-variant">{[title(r.relationship), title(r.gender), r.dob && fmtDate(r.dob)].filter(Boolean).join(' · ')}</div>
            </td>
            <td>{r.family_name}</td>
            <td>
              <div>{r.requested_by_name ?? '—'}</div>
              <div className="text-xs text-on-surface-variant">{fmtDateTime(r.created_at)}</div>
            </td>
            <td>
              <StatusBadge status={r.status} />
              {r.rejection_reason && <div className="mt-1 max-w-56 text-xs text-on-surface-variant">{r.rejection_reason}</div>}
            </td>
            <td className="text-right">
              {r.status === 'PENDING' && (
                <Decide small onApprove={() => decide(r, 'approve')} onReject={(reason) => decide(r, 'reject', { reason })} />
              )}
            </td>
          </tr>
        ))}
      </Table>
      {list.data && <Pager total={list.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />}

      <h2 className="mt-10 mb-3 font-display text-xl font-semibold text-secondary">Decision history</h2>
      <Card>
        {log.error ? <div className="p-4"><ErrorText>{log.error}</ErrorText></div>
          : log.loading && !log.data ? <p className="p-4 text-sm text-on-surface-variant">Loading…</p>
          : !log.data?.items.length ? <p className="p-4 text-sm text-on-surface-variant">No decisions yet.</p>
          : (
            <ol className="divide-y divide-outline-variant">
              {log.data.items.map((d) => (
                <li key={d.family_member_id} className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-4 py-3 text-sm">
                  <time className="w-40 shrink-0 text-xs text-on-surface-variant">{fmtDateTime(d.reviewed_at)}</time>
                  <StatusBadge status={d.status} />
                  <div className="min-w-0 flex-1">
                    <span className="font-semibold">{d.reviewed_by_name ?? 'City admin'}</span>
                    {d.status === 'APPROVED' ? ' approved ' : ' rejected '}
                    <span className="font-semibold">{d.full_name}</span>
                    <span className="text-on-surface-variant"> ({title(d.relationship)}) · {d.family_name} household · requested by {d.requested_by_name ?? '—'}</span>
                    {d.rejection_reason && <div className="text-xs text-on-surface-variant">Reason: {d.rejection_reason}</div>}
                  </div>
                </li>
              ))}
            </ol>
          )}
      </Card>
      {log.data && <Pager total={log.data.total} limit={LOG_LIMIT} offset={logOffset} onChange={setLogOffset} />}
    </>
  )
}
