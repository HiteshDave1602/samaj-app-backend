import { useState } from 'react'
import { download, fmtDateTime, qs, useLoad, useSubmit, useToast } from '../../shared/api'
import { Button, Card, ErrorText, Field, PageHeader, Pager, Table, inputCls } from '../../shared/ui'

const LIMIT = 20
const STATUSES = [['ACTIVE', 'Active'], ['PENDING', 'Pending'], ['REJECTED', 'Rejected'], ['ARCHIVED', 'Archived']]
// FR-84: the only columns the API allows. Biodata can't be exported.
const COLUMNS = [['full_name', 'Full name'], ['gender', 'Gender'], ['dob', 'Date of birth'], ['age', 'Age'], ['mobile', 'Mobile'],
  ['address', 'Address'], ['family_name', 'Family name'], ['native_place', 'Native place'], ['status', 'Status'], ['member_since', 'Member since']]
const LABEL = Object.fromEntries([...STATUSES, ...COLUMNS])

const Checks = ({ name, options, checked }) => (
  <div className="flex flex-wrap gap-x-5 gap-y-2">
    {options.map(([v, l]) => (
      <label key={v} className="flex items-center gap-2 text-sm">
        <input type="checkbox" name={name} value={v} defaultChecked={checked(v)} className="h-4 w-4 accent-primary" />{l}
      </label>
    ))}
  </div>
)

export default function Export() {
  const [offset, setOffset] = useState(0)
  const jobs = useLoad(`/cityadmin/exports${qs({ limit: LIMIT, offset })}`)
  const toast = useToast()

  const { onSubmit, busy, error } = useSubmit(async (f, fd) => {
    const status = fd.getAll('status')
    const columns = fd.getAll('columns')
    if (!status.length) throw new Error('Pick at least one status')
    if (!columns.length) throw new Error('Pick at least one column')
    const filters = { status }
    for (const k of ['gender', 'area', 'family_name']) if (f[k].trim()) filters[k] = f[k].trim()
    for (const k of ['age_min', 'age_max']) if (f[k] !== '') filters[k] = Number(f[k])
    const res = await download('/cityadmin/exports', 'members.xlsx', { method: 'POST', body: { filters, columns, password: f.password } })
    toast(`Exported ${res.headers.get('X-Row-Count')} members. Share the password separately.`)
    jobs.reload()
  })

  return (
    <>
      <PageHeader title="Export members" subtitle="Download your city's members as a password-protected Excel file. The password is never stored; every export is logged." />
      <Card className="mb-8 p-5">
        <form onSubmit={onSubmit} className="grid gap-5 sm:grid-cols-2">
          <Field label="Status" className="sm:col-span-2"><Checks name="status" options={STATUSES} checked={(v) => v === 'ACTIVE'} /></Field>
          <Field label="Gender">
            <select name="gender" defaultValue="" className={inputCls}>
              <option value="">Any</option>
              <option value="MALE">Male</option>
              <option value="FEMALE">Female</option>
              <option value="OTHER">Other</option>
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Age from"><input name="age_min" type="number" min={0} max={120} className={inputCls} /></Field>
            <Field label="Age to"><input name="age_max" type="number" min={0} max={120} className={inputCls} /></Field>
          </div>
          <Field label="Area" hint="Matched in the address and native place"><input name="area" maxLength={120} className={inputCls} /></Field>
          <Field label="Family name"><input name="family_name" maxLength={120} className={inputCls} /></Field>
          <Field label="Columns" className="sm:col-span-2"><Checks name="columns" options={COLUMNS} checked={() => true} /></Field>
          <Field label="File password" hint="At least 8 characters. Needed to open the file." className="sm:col-span-2 sm:max-w-sm">
            <input name="password" type="password" required minLength={8} maxLength={128} autoComplete="new-password" className={inputCls} />
          </Field>
          <div className="sm:col-span-2"><ErrorText>{error}</ErrorText></div>
          <div className="flex justify-end sm:col-span-2">
            <Button type="submit" disabled={busy}>{busy ? 'Preparing…' : 'Download Excel'}</Button>
          </div>
        </form>
      </Card>

      <h2 className="mb-4 text-xl leading-7 font-semibold">Export history</h2>
      <Table head={['When', 'Members', 'Filters', 'Columns']} error={jobs.error} loading={jobs.loading} empty="No exports yet.">
        {jobs.data?.items.map((j) => (
          <tr key={j.export_job_id}>
            <td className="whitespace-nowrap">{fmtDateTime(j.created_at)}</td>
            <td>{j.row_count}</td>
            <td className="text-xs text-on-surface-variant">{describe(j.filters)}</td>
            <td className="text-xs text-on-surface-variant">{j.columns_exported.length === COLUMNS.length ? 'All' : j.columns_exported.map((c) => LABEL[c] ?? c).join(', ')}</td>
          </tr>
        ))}
      </Table>
      {jobs.data && <Pager total={jobs.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />}
    </>
  )
}

const describe = (f) => Object.entries(f).filter(([, v]) => v != null && v !== '')
  .map(([k, v]) => `${k.replace('_', ' ')}: ${Array.isArray(v) ? v.map((s) => LABEL[s] ?? s).join(', ') : v}`).join(' · ')
