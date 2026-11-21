import { useState } from 'react'
import { api, download, fmtDateTime, qs, useLoad, useToast } from '../../shared/api'
import { Button, Card, ErrorText, Field, Modal, PageHeader, Pager, StatusBadge, Table, Toolbar, inputCls } from '../../shared/ui'

const LIMIT = 20
const ROWS = 100
const BASE = '/superadmin/imports'

// Directory import: each row names its city (Section); a Self row and the rows below it are one family.
export default function Import() {
  const [offset, setOffset] = useState(0)
  const [open, setOpen] = useState(null) // import_job_id
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const jobs = useLoad(`${BASE}${qs({ limit: LIMIT, offset })}`)

  async function template(format) {
    setError(null)
    try { await download(`${BASE}/template?file_format=${format}`, `samaj-directory-import.${format.toLowerCase()}`) } catch (e) { setError(e.message) }
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
      const job = await api(BASE, { method: 'POST', form })
      jobs.reload()
      setOpen(job.import_job_id)
    } catch (x) { setError(x.message) } finally { setBusy(false) }
  }

  return (
    <>
      <PageHeader title="Import directory" subtitle="Add families to the app directory from a sheet. Put each family's head first (Relation: Self); the rows below it, up to the next Self row, are that family. A Section (City) the app doesn't have yet is added as a new city when you import (set its state later in Cities). Uploading only checks the file; nothing changes until you import it. People don't get an app login: they register in the app, or a member adds them to their family tree.">
        <Button variant="outline" onClick={() => template('XLSX')}>Excel template</Button>
        <Button variant="outline" onClick={() => template('CSV')}>CSV template</Button>
      </PageHeader>

      <Card className="mb-8 flex flex-wrap items-center gap-4 p-5">
        <label className={`inline-flex h-10 cursor-pointer items-center rounded-full bg-primary px-[18px] text-sm font-semibold text-on-primary hover:bg-primary-hover ${busy ? 'pointer-events-none opacity-50' : ''}`}>
          {busy ? 'Checking…' : 'Upload a file'}
          <input type="file" accept=".csv,.xlsx" onChange={upload} disabled={busy} className="sr-only" />
        </label>
        <p className="text-sm text-on-surface-variant">.csv or .xlsx, up to 10 MB. Columns: Section (City), Name, Relation, Gotra / Vatan, Date of Birth, Education, Marital Status, Occupation, Hobby, Blood Group, Address, Mobile.</p>
        <div className="w-full"><ErrorText>{error}</ErrorText></div>
      </Card>

      <h2 className="mb-4 text-xl leading-7 font-semibold">Past imports</h2>
      <Table head={['Uploaded', 'Rows', 'New', 'Updates', 'Errors', 'Status', '']} error={jobs.error} loading={jobs.loading} empty="No imports yet.">
        {jobs.data?.items.map((j) => (
          <tr key={j.import_job_id}>
            <td className="whitespace-nowrap">{fmtDateTime(j.created_at)}<div className="text-xs text-on-surface-variant">{j.file_format}</div></td>
            <td>{j.total_rows ?? '—'}</td>
            <td>{j.new_count}</td>
            <td>{j.updated_count}</td>
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
  const job = useLoad(`${BASE}/${id}`)
  const rows = useLoad(`${BASE}/${id}/rows${qs({ outcome, limit: ROWS, offset })}`)
  const toast = useToast()
  const j = job.data

  async function commit() {
    if (!confirm(`Add ${j.new_count} ${j.new_count === 1 ? 'person' : 'people'} and update ${j.updated_count}? Rows with errors are skipped.`)) return
    setBusy(true)
    setError(null)
    try {
      await api(`${BASE}/${id}/commit`, { method: 'POST' })
      toast('Imported')
      job.reload()
      rows.reload()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <Modal title="Directory import" onClose={onClose} wide>
      {job.error ? <ErrorText>{job.error}</ErrorText> : !j ? <p className="text-on-surface-variant">Loading…</p> : (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-3 gap-2">
            {[['New', j.new_count], ['Updates', j.updated_count], ['Errors', j.error_count]].map(([l, v]) => (
              <div key={l} className="rounded-lg bg-surface-variant px-3 py-2">
                <div className="text-xs font-semibold text-on-surface-variant">{l}</div>
                <div className="font-display text-2xl font-bold text-secondary">{v}</div>
              </div>
            ))}
          </div>
          <p className="text-sm text-on-surface-variant">
            {j.status === 'DRY_RUN_READY'
              ? 'Checked, not imported yet. Updates are people already in that family (same city, head and name): their details are replaced with the file\'s.'
              : `Imported ${fmtDateTime(j.committed_at)}. These people are now in the app directory.`}
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
                <option value="ERROR">Errors</option>
                <option value="NEW">New</option>
                <option value="UPDATE">Updates</option>
              </select>
            </Field>
          </Toolbar>
          <Table head={['Row', 'Name', 'Mobile', 'Outcome']} error={rows.error} loading={rows.loading} empty="No rows.">
            {rows.data?.items.map((r) => (
              <tr key={r.row_number}>
                <td className="font-mono text-xs">{r.row_number}</td>
                <td>{r.full_name ?? '—'}{r.error_message && <div className={`text-xs ${r.outcome === 'ERROR' ? 'text-error' : 'text-on-surface-variant'}`}>{r.error_message}</div>}</td>
                <td className="font-mono text-xs whitespace-nowrap">{r.mobile_last4 ? `•••• ${r.mobile_last4}` : '—'}</td>
                <td><div className="flex flex-wrap gap-1"><StatusBadge status={r.outcome} />{r.resolution && <StatusBadge status={r.resolution} />}</div></td>
              </tr>
            ))}
          </Table>
          {rows.data && <Pager total={rows.data.total} limit={ROWS} offset={offset} onChange={setOffset} />}
        </div>
      )}
    </Modal>
  )
}
