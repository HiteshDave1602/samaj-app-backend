import { useState } from 'react'
import { api, fmtDate, fmtDateTime, qs, useLoad, useToast } from '../../shared/api'
import { Field, PageHeader, Pager, StatusBadge, Table, Toolbar, inputCls } from '../../shared/ui'
import Decide from '../Decide'

const LIMIT = 50
const title = (s) => s && s[0] + s.slice(1).toLowerCase().replaceAll('_', ' ')

export default function FamilyAdditions() {
  const [status, setStatus] = useState('PENDING')
  const [offset, setOffset] = useState(0)
  const list = useLoad(`/cityadmin/family-additions${qs({ status, limit: LIMIT, offset })}`)
  const toast = useToast()

  async function decide(r, action, body) {
    await api(`/cityadmin/family-additions/${r.family_member_id}/${action}`, { method: 'POST', body })
    toast(`${r.full_name} ${action === 'approve' ? 'added to the family' : 'rejected'}`)
    list.reload()
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
    </>
  )
}
