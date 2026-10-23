import { useState } from 'react'
import { api, download, fmtDateTime, qs, useLoad, useToast } from '../../shared/api'
import { Button, Card, ErrorText, Field, Modal, PageHeader, Pager, StatusBadge, Table, Toolbar, inputCls } from '../../shared/ui'

const LIMIT = 20
const ROWS = 100

export default function Import() {
  const [offset, setOffset] = useState(0)
  const [open, setOpen] = useState(null) // import_job_id
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const jobs = useLoad(`/cityadmin/imports${qs({ limit: LIMIT, offset })}`)

  async function template(format) {
    setError(null)
    try { await download(`/cityadmin/imports/template?file_format=${format}`, `samaj-member-import.${format.toLowerCase()}`) } catch (e) { setError(e.message) }
  }

  async function upload(e) {
    const file = e.target.files[0]
    e.target.value = '' // the same file can be picked again after fixing it
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    setBusy(true)
    setError(null)
    try {
      const job = await api('/cityadmin/imports', { method: 'POST', form })
      jobs.reload()
      setOpen(job.import_job_id)
    } catch (x) { setError(x.message) } finally { setBusy(false) }
  }

  return (
    <>
      <PageHeader title="Import members" subtitle="Bring in your community's existing member list. Uploading only checks the file; nothing changes until you import it. Imported members are active straight away.">
        <Button variant="outline" onClick={() => template('XLSX')}>Excel template</Button>
        <Button variant="outline" onClick={() => template('CSV')}>CSV template</Button>
      </PageHeader>

      <Card className="mb-8 flex flex-wrap items-center gap-4 p-5">
        <label className={`inline-flex h-10 cursor-pointer items-center rounded-full bg-primary px-[18px] text-sm font-semibold text-on-primary hover:bg-primary-hover ${busy ? 'pointer-events-none opacity-50' : ''}`}>
          {busy ? 'Checking…' : 'Upload a file'}
          <input type="file" accept=".csv,.xlsx" onChange={upload} disabled={busy} className="sr-only" />
        </label>
        <p className="text-sm text-on-surface-variant">.csv or .xlsx, up to 10 MB. Keep the template's column headers exactly as they are.</p>
        <div className="w-full"><ErrorText>{error}</ErrorText></div>
      </Card>

      <h2 className="mb-4 text-xl leading-7 font-semibold">Past imports</h2>
      <Table head={['Uploaded', 'Rows', 'New', 'Updates', 'Conflicts', 'Errors', 'Status', '']} error={jobs.error} loading={jobs.loading} empty="No imports yet.">
        {jobs.data?.items.map((j) => (
          <tr key={j.import_job_id}>
            <td className="whitespace-nowrap">{fmtDateTime(j.created_at)}<div className="text-xs text-on-surface-variant">{j.file_format}</div></td>
            <td>{j.total_rows ?? '—'}</td>
            <td>{j.new_count}</td>
            <td>{j.updated_count}</td>
            <td>{j.conflict_count}</td>
            <td>{j.error_count}</td>
            <td><StatusBadge status={j.status} /></td>
            <td className="text-right"><Button variant="text" className="h-8 px-3" onClick={() => setOpen(j.import_job_id)}>Open</Button></td>
          </tr>
        ))}
      </Table>
      {jobs.data && <Pager total={jobs.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />}
      {open && <Job id={open} onClose={() => { setOpen(null); jobs.reload() }} />}
    </>
  )
}

function Job({ id, onClose }) {
  const [outcome, setOutcome] = useState('')
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const job = useLoad(`/cityadmin/imports/${id}`)
  const rows = useLoad(`/cityadmin/imports/${id}/rows${qs({ outcome, limit: ROWS, offset })}`)
  const toast = useToast()
  const j = job.data

  async function run(fn) {
    setBusy(true)
    setError(null)
    try { await fn() } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const commit = () => run(async () => {
    if (!confirm(`Add ${j.new_count} new member${j.new_count === 1 ? '' : 's'} and update ${j.updated_count}? Rows with errors are skipped.`)) return
    await api(`/cityadmin/imports/${id}/commit`, { method: 'POST' })
    toast('Imported')
    job.reload()
    rows.reload()
  })

  const resolve = (row, action) => run(async () => {
    await api(`/cityadmin/imports/${id}/rows/${row.row_number}/resolve`, { method: 'POST', body: { action } })
    toast(`Row ${row.row_number} ${action === 'APPLY' ? 'applied' : 'skipped'}`)
    rows.reload()
  })

  return (
    <Modal title="Import" onClose={onClose} wide>
      {job.error ? <ErrorText>{job.error}</ErrorText> : !j ? <p className="text-on-surface-variant">Loading…</p> : (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[['New', j.new_count], ['Updates', j.updated_count], ['Conflicts', j.conflict_count], ['Errors', j.error_count]].map(([l, v]) => (
              <div key={l} className="rounded-lg bg-surface-variant px-3 py-2">
                <div className="text-xs font-semibold text-on-surface-variant">{l}</div>
                <div className="font-display text-2xl font-bold text-secondary">{v}</div>
              </div>
            ))}
          </div>
          <p className="text-sm text-on-surface-variant">
            {j.status === 'DRY_RUN_READY'
              ? 'Checked, not imported yet. Conflicts are numbers already registered under a different name or date of birth: decide each one now or after importing.'
              : `Imported ${fmtDateTime(j.committed_at)}. Decide any conflicts left below.`}
          </p>
          <ErrorText>{error}</ErrorText>
          {j.status === 'DRY_RUN_READY' && (
            <div className="flex justify-end">
              <Button onClick={commit} disabled={busy || j.new_count + j.updated_count === 0}>Import {j.new_count + j.updated_count} rows</Button>
            </div>
          )}

          <Toolbar>
            <Field label="Rows">
              <select value={outcome} onChange={(e) => { setOutcome(e.target.value); setOffset(0) }} className={inputCls}>
                <option value="">All</option>
                <option value="CONFLICT">Conflicts</option>
                <option value="ERROR">Errors</option>
                <option value="NEW">New</option>
                <option value="UPDATE">Updates</option>
              </select>
            </Field>
          </Toolbar>
          <Table head={['Row', 'Name', 'Mobile', 'Outcome', '']} error={rows.error} loading={rows.loading} empty="No rows.">
            {rows.data?.items.map((r) => (
              <tr key={r.row_number}>
                <td className="font-mono text-xs">{r.row_number}</td>
                <td>{r.full_name ?? '—'}{r.error_message && <div className="text-xs text-error">{r.error_message}</div>}</td>
                <td className="font-mono text-xs whitespace-nowrap">{r.mobile_last4 ? `•••• ${r.mobile_last4}` : '—'}</td>
                <td><div className="flex flex-wrap gap-1"><StatusBadge status={r.outcome} />{r.resolution && <StatusBadge status={r.resolution} />}</div></td>
                <td className="text-right whitespace-nowrap">
                  {r.outcome === 'CONFLICT' && !r.resolution && (
                    <>
                      <Button variant="text" className="h-8 px-3" disabled={busy} onClick={() => resolve(r, 'SKIP')} title="Keep the member as they are">Keep</Button>
                      <Button variant="outline" className="h-8 px-3" disabled={busy} onClick={() => resolve(r, 'APPLY')} title="Overwrite the member's name, date of birth and details with this row">Use file</Button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </Table>
          {rows.data && <Pager total={rows.data.total} limit={ROWS} offset={offset} onChange={setOffset} />}
        </div>
      )}
    </Modal>
  )
}
