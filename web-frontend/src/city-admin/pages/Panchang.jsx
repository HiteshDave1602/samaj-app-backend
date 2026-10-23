import { useState } from 'react'
import { api, fmtDate, fmtDateTime, qs, useLoad, useSubmit, useToast } from '../../shared/api'
import { Badge, Button, ErrorText, Field, FormActions, Modal, PageHeader, StatusBadge, Table, Toolbar, inputCls } from '../../shared/ui'

// Dates are plain YYYY-MM-DD in IST, as the API uses them.
const todayIST = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date())
const addDays = (d, n) => new Date(Date.parse(`${d}T00:00Z`) + n * 864e5).toISOString().slice(0, 10)
const fmtDay = (d) => fmtDate(`${d}T00:00`)

export default function Panchang() {
  const [range, setRange] = useState(() => ({ from: todayIST(), to: addDays(todayIST(), 6) }))
  const [editing, setEditing] = useState(null) // a date
  const status = useLoad('/cityadmin/panchang/status')
  const list = useLoad(`/cityadmin/panchang${qs({ date_from: range.from, date_to: range.to })}`)
  const byDate = Object.fromEntries(list.data?.map((d) => [d.panchang_date, d]) ?? [])
  const days = []
  for (let d = range.from; d <= range.to && days.length <= 92; d = addDays(d, 1)) days.push(d)
  const s = status.data

  return (
    <>
      <PageHeader title="Panchang" subtitle="One Panchang for every city. It's fetched automatically; enter a day by hand when the fetch fails or a value is wrong. Manual entries win over fetched ones." />
      {s?.error_code && (
        <div role="alert" className="mb-6 rounded-xl border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
          <b>Today's Panchang is missing.</b> {s.message} <button type="button" onClick={() => setEditing(s.date)} className="font-semibold underline">Enter today</button>
        </div>
      )}
      <Toolbar>
        <Field label="From"><input type="date" value={range.from} onChange={(e) => e.target.value && setRange((r) => ({ ...r, from: e.target.value }))} className={inputCls} /></Field>
        <Field label="To" hint="Up to 92 days"><input type="date" value={range.to} min={range.from} onChange={(e) => e.target.value && setRange((r) => ({ ...r, to: e.target.value }))} className={inputCls} /></Field>
      </Toolbar>
      <Table head={['Date', 'Tithi', 'Nakshatra', 'Yoga', 'Source', '']} error={list.error} loading={list.loading} empty="Pick a date range.">
        {(list.data ? days : []).map((d) => {
          const p = byDate[d]
          return (
            <tr key={d} className={d === s?.date ? 'bg-primary-container/40' : ''}>
              <td className="font-semibold whitespace-nowrap">{fmtDay(d)}{d === s?.date && <span className="ml-2 text-xs font-normal text-on-surface-variant">today</span>}</td>
              {p ? (
                <>
                  <td>{p.tithi}</td>
                  <td>{p.nakshatra}</td>
                  <td>{p.yoga}</td>
                  <td>
                    <StatusBadge status={p.source} />
                    {p.edited_by_name && <div className="mt-1 text-xs text-on-surface-variant">{p.edited_by_name}</div>}
                  </td>
                </>
              ) : <td colSpan={4}><Badge tone="warning">Missing</Badge></td>}
              <td className="text-right">
                <Button variant="text" className="h-8 px-3" onClick={() => setEditing(d)}>{p ? 'Correct' : 'Enter'}</Button>
              </td>
            </tr>
          )
        })}
      </Table>
      {editing && (
        <DayForm date={editing} day={byDate[editing]} onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); list.reload(); status.reload() }} />
      )}
    </>
  )
}

function DayForm({ date, day, onClose, onSaved }) {
  const detail = useLoad(day ? `/cityadmin/panchang/${date}` : null)
  const toast = useToast()
  const { onSubmit, busy, error } = useSubmit(async ({ tithi, nakshatra, yoga }) => {
    await api(`/cityadmin/panchang/${date}`, { method: 'PUT', body: { tithi, nakshatra, yoga, verified_against_calendar: true } })
    toast(`Panchang saved for ${fmtDay(date)}`)
    onSaved()
  })
  return (
    <Modal title={`Panchang · ${fmtDay(date)}`} onClose={onClose} wide>
      <form onSubmit={onSubmit} className="grid gap-4 sm:grid-cols-3">
        <Field label="Tithi"><input name="tithi" required maxLength={40} defaultValue={day?.tithi} autoFocus className={inputCls} /></Field>
        <Field label="Nakshatra"><input name="nakshatra" required maxLength={40} defaultValue={day?.nakshatra} className={inputCls} /></Field>
        <Field label="Yoga"><input name="yoga" required maxLength={40} defaultValue={day?.yoga} className={inputCls} /></Field>
        <label className="flex items-start gap-2 text-sm sm:col-span-3">
          <input type="checkbox" required className="mt-0.5 h-4 w-4 accent-primary" />
          I checked these values against the Samaj calendar.
        </label>
        <div className="sm:col-span-3"><ErrorText>{error}</ErrorText></div>
        <div className="sm:col-span-3"><FormActions busy={busy} label="Publish" onCancel={onClose} /></div>
      </form>
      {detail.data?.revisions.length > 0 && (
        <div className="mt-6">
          <h3 className="mb-2 text-xs font-semibold tracking-[.5px] text-on-surface-variant uppercase">History</h3>
          <Table head={['When', 'By', 'Tithi', 'Nakshatra', 'Yoga']}>
            {detail.data.revisions.map((r) => (
              <tr key={r.revision_id}>
                <td className="text-xs whitespace-nowrap">{fmtDateTime(r.created_at)}</td>
                <td className="text-xs">{r.edited_by_name ?? (r.source === 'API' ? 'Automatic fetch' : '—')}</td>
                <td>{r.tithi}</td>
                <td>{r.nakshatra}</td>
                <td>{r.yoga}</td>
              </tr>
            ))}
          </Table>
        </div>
      )}
    </Modal>
  )
}
