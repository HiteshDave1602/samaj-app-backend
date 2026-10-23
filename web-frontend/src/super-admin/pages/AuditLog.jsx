import { Fragment, useState } from 'react'
import { api, fmtDateTime, qs, useLoad } from '../api'
import { Button, ErrorText, Field, PageHeader, Pager, Table, Toolbar, inputCls } from '../ui'

const LIMIT = 50
const EMPTY = { date_from: '', date_to: '', action: '', city_id: '' }

export default function AuditLog() {
  const [filters, setFilters] = useState(EMPTY)
  const [offset, setOffset] = useState(0)
  const [open, setOpen] = useState(null)
  const [exportError, setExportError] = useState(null)
  const cities = useLoad('/superadmin/cities')
  const query = { ...filters, action: filters.action.trim().toUpperCase() }
  const list = useLoad(`/superadmin/audit-logs${qs({ ...query, limit: LIMIT, offset })}`)
  const set = (k) => (e) => { setFilters((f) => ({ ...f, [k]: e.target.value })); setOffset(0) }

  async function exportCsv() {
    setExportError(null)
    try {
      const res = await api(`/superadmin/audit-logs/export.csv${qs(query)}`, { raw: true })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(await res.blob())
      a.download = 'audit-log.csv'
      a.click()
      URL.revokeObjectURL(a.href)
    } catch (e) { setExportError(e.message) }
  }

  return (
    <>
      <PageHeader title="Audit Log" subtitle="Every admin action, newest first. Select a row to see what changed.">
        <Button variant="outline" onClick={exportCsv}>Export CSV</Button>
      </PageHeader>
      <Toolbar>
        <Field label="From"><input type="date" value={filters.date_from} onChange={set('date_from')} className={inputCls} /></Field>
        <Field label="To"><input type="date" value={filters.date_to} onChange={set('date_to')} className={inputCls} /></Field>
        <Field label="Action"><input value={filters.action} onChange={set('action')} placeholder="e.g. CITY_CREATE" maxLength={40} className={`${inputCls} font-mono`} /></Field>
        <Field label="City">
          <select value={filters.city_id} onChange={set('city_id')} className={inputCls}>
            <option value="">All cities</option>
            {cities.data?.map((c) => <option key={c.city_id} value={c.city_id}>{c.name}</option>)}
          </select>
        </Field>
        {Object.values(filters).some(Boolean) && <Button variant="text" onClick={() => { setFilters(EMPTY); setOffset(0) }}>Clear</Button>}
      </Toolbar>
      <div className="mb-3"><ErrorText>{exportError}</ErrorText></div>
      <Table head={['When', 'Who', 'Action', 'Target', 'City', 'IP']} error={list.error} loading={list.loading} empty="No entries match these filters.">
        {list.data?.items.map((e) => (
          <Fragment key={e.audit_id}>
            <tr onClick={() => setOpen(open === e.audit_id ? null : e.audit_id)} aria-expanded={open === e.audit_id}
              className={`cursor-pointer hover:bg-surface-variant/60 ${open === e.audit_id ? 'bg-surface-variant/60' : ''}`}>
              <td className="whitespace-nowrap">{fmtDateTime(e.occurred_at)}</td>
              <td>{e.actor_name ?? <span className="text-on-surface-variant">{e.actor_type.toLowerCase()}</span>}</td>
              <td><span className="font-mono text-xs font-semibold text-secondary">{e.action}</span></td>
              <td className="text-xs text-on-surface-variant">{e.target_table}</td>
              <td>{e.city_name ?? '—'}</td>
              <td className="font-mono text-xs">{e.source_ip ?? '—'}</td>
            </tr>
            {open === e.audit_id && (
              <tr><td colSpan={6} className="bg-surface-variant/40"><Changes entry={e} /></td></tr>
            )}
          </Fragment>
        ))}
      </Table>
      {list.data && <Pager total={list.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />}
    </>
  )
}

const show = (v) => (v == null ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v))

function Changes({ entry }) {
  const before = entry.before_state ?? {}
  const after = entry.after_state ?? {}
  const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])]
  return (
    <div className="py-1">
      <div className="mb-2 font-mono text-xs text-on-surface-variant">{entry.target_table} · {entry.target_id ?? 'no target id'}</div>
      {keys.length === 0 ? <p className="text-on-surface-variant">No field changes recorded.</p> : (
        <table className="w-full text-xs [&_td]:border-0! [&_td]:py-1! [&_td]:pl-0!">
          <thead><tr className="text-left text-on-surface-variant"><th className="w-40 pb-1">Field</th><th className="pb-1">Before</th><th className="pb-1">After</th></tr></thead>
          <tbody>
            {keys.map((k) => (
              <tr key={k}>
                <td className="font-mono font-semibold">{k}</td>
                <td className="font-mono break-all text-on-surface-variant">{k in before ? show(before[k]) : ''}</td>
                <td className="font-mono break-all">{k in after ? show(after[k]) : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
