import { useState } from 'react'
import { api, fmtDateTime, qs, useLoad, useSubmit, useToast } from './api'
import { Badge, Button, ErrorText, Field, FormActions, Modal, PageHeader, Pager, StatusBadge, Table, Toolbar, inputCls } from './ui'
import Decide from '../city-admin/Decide'

const LIMIT = 20

// <input type="datetime-local"> works in local time without a zone; the API wants aware ISO times.
const toLocalInput = (iso) => {
  const d = iso ? new Date(iso) : new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 16)
}
const toIso = (local) => new Date(local).toISOString()

// Both panels. A City Admin works on their own city only, so there is no audience to pick.
export default function Content({ me }) {
  const cityAdmin = me.role === 'CITY_ADMIN'
  const base = cityAdmin ? '/cityadmin/content' : '/superadmin/content'
  const [filters, setFilters] = useState({ content_type: '', status: '', scope: '' })
  const [offset, setOffset] = useState(0)
  const [editing, setEditing] = useState(null) // {} for new
  const cities = useLoad(cityAdmin ? null : '/superadmin/cities')
  const scope = filters.scope === 'all' ? { all_cities: true } : { city_id: filters.scope }
  const list = useLoad(`${base}${qs({ content_type: filters.content_type, status: filters.status, ...scope, limit: LIMIT, offset })}`)
  const cityName = Object.fromEntries(cities.data?.map((c) => [c.city_id, c.name]) ?? [])
  const set = (k) => (e) => { setFilters((f) => ({ ...f, [k]: e.target.value })); setOffset(0) }
  const toast = useToast()

  // member-submitted news (City Admin only): approving puts it live now
  async function decide(c, action, body) {
    await api(`${base}/${c.content_id}/${action}`, { method: 'POST', body })
    toast(action === 'approve' ? `"${c.title}" is live` : 'Rejected')
    list.reload()
  }

  return (
    <>
      <PageHeader title="News & Ads" subtitle={`${cityAdmin ? `Publish to members in ${me.city_name}.` : 'Publish to one city or to every city.'} Items go live at their start time and expire at their end time.`}>
        <Button onClick={() => setEditing({})}>Create</Button>
      </PageHeader>
      <Toolbar>
        <Field label="Type">
          <select value={filters.content_type} onChange={set('content_type')} className={inputCls}>
            <option value="">News and ads</option>
            <option value="NEWS">News</option>
            <option value="AD">Ads</option>
          </select>
        </Field>
        <Field label="Status">
          <select value={filters.status} onChange={set('status')} className={inputCls}>
            <option value="">Any</option>
            {['PENDING', 'LIVE', 'SCHEDULED', 'DRAFT', 'EXPIRED', 'CANCELLED', 'REJECTED'].map((s) => <option key={s} value={s}>{s[0] + s.slice(1).toLowerCase()}</option>)}
          </select>
        </Field>
        {!cityAdmin && (
          <Field label="Audience">
            <select value={filters.scope} onChange={set('scope')} className={inputCls}>
              <option value="">Everything</option>
              <option value="all">All-city items only</option>
              {cities.data?.map((c) => <option key={c.city_id} value={c.city_id}>{c.name}</option>)}
            </select>
          </Field>
        )}
      </Toolbar>
      <Table head={cityAdmin ? ['Item', 'Runs', 'Status', ''] : ['Item', 'Audience', 'Runs', 'Status', '']} error={list.error} loading={list.loading} empty="No news or ads match.">
        {list.data?.items.map((c) => (
          <tr key={c.content_id}>
            <td>
              <div className="flex items-start gap-3">
                {c.media_url && <img src={c.media_url} alt="" className="h-12 w-12 shrink-0 rounded-lg border border-outline-variant object-cover" />}
                <div className="min-w-0">
                  <div className="mb-1 flex flex-wrap gap-1.5">
                    <Badge tone={c.content_type === 'AD' ? 'accent' : 'secondary'}>{c.content_type === 'AD' ? 'Ad' : 'News'}</Badge>
                    {c.creative_format && <Badge>{c.creative_format === 'FULLSCREEN' ? 'Full screen' : 'Banner'}</Badge>}
                    {c.created_by_member_id && <Badge>From a member</Badge>}
                  </div>
                  <div className="font-semibold">{c.title}</div>
                  {c.status === 'PENDING' && (
                    <>
                      <p className="mt-1 max-w-md text-xs whitespace-pre-line text-on-surface-variant">{c.body}</p>
                      <div className="mt-2 flex gap-2">
                        {c.extra_media_urls.map((u) => <a key={u} href={u} target="_blank" rel="noreferrer"><img src={u} alt="" className="h-12 w-12 rounded-lg border border-outline-variant object-cover" /></a>)}
                      </div>
                    </>
                  )}
                </div>
              </div>
            </td>
            {!cityAdmin && <td>{c.city_id ? cityName[c.city_id] ?? '…' : <Badge tone="primary">All cities</Badge>}</td>}
            <td className="text-xs whitespace-nowrap text-on-surface-variant">{fmtDateTime(c.start_at)}<br />to {fmtDateTime(c.end_at)}</td>
            <td><StatusBadge status={c.status} /></td>
            <td className="text-right">
              {c.status === 'PENDING' && cityAdmin && <Decide small onApprove={() => decide(c, 'approve')} onReject={(reason) => decide(c, 'reject', { reason })} />}
              {!['EXPIRED', 'CANCELLED', 'PENDING', 'REJECTED'].includes(c.status) && <Button variant="text" className="h-8 px-3" onClick={() => setEditing(c)}>Edit</Button>}
            </td>
          </tr>
        ))}
      </Table>
      {list.data && <Pager total={list.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />}
      {editing && (
        <ContentForm item={editing} base={base} cities={cityAdmin ? null : cities.data?.filter((c) => c.is_active || c.city_id === editing.city_id) ?? []}
          onClose={() => setEditing(null)} onSaved={() => { setEditing(null); list.reload() }} />
      )}
    </>
  )
}

/** cities: null for a City Admin (always their own city). */
function ContentForm({ item, base, cities, onClose, onSaved }) {
  const isNew = !item.content_id
  const [type, setType] = useState(item.content_type ?? 'NEWS')
  const [media, setMedia] = useState(item.media_key ? { media_key: item.media_key, media_url: item.media_url, width: item.media_width, height: item.media_height } : null)
  const [uploadError, setUploadError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const toast = useToast()

  async function upload(e) {
    const file = e.target.files[0]
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    setUploading(true)
    setUploadError(null)
    try { setMedia(await api(`${base}/media`, { method: 'POST', form })) } catch (x) { setUploadError(x.message) } finally { setUploading(false) }
  }

  async function cancelItem() {
    if (!confirm(`Cancel "${item.title}"? Cancelled items can't be changed again.`)) return
    try {
      await api(`${base}/${item.content_id}`, { method: 'PUT', body: { status: 'CANCELLED' } })
      toast('Cancelled')
      onSaved()
    } catch (x) { setUploadError(x.message) }
  }

  const { onSubmit, busy, error } = useSubmit(async (f) => {
    if (type === 'AD' && !media) throw new Error('Upload the ad image first')
    const body = {
      title: f.title,
      start_at: toIso(f.start_at),
      end_at: toIso(f.end_at),
      status: f.status,
      ...(type === 'NEWS' ? { body: f.body } : { creative_format: f.creative_format }),
      ...(media && media.media_key !== item.media_key ? { media_key: media.media_key } : {}),
    }
    if (isNew) {
      await api(base, { method: 'POST', body: { ...body, content_type: type, city_id: f.city_id || null, media_key: media?.media_key } })
    } else {
      await api(`${base}/${item.content_id}`, { method: 'PUT', body })
    }
    toast(isNew ? (f.status === 'DRAFT' ? 'Saved as draft' : 'Scheduled') : 'Saved')
    onSaved()
  })

  const [weekLater] = useState(() => new Date(Date.now() + 7 * 864e5).toISOString())
  return (
    <Modal title={isNew ? 'Create news or ad' : `Edit ${type === 'AD' ? 'ad' : 'news'}`} onClose={onClose} wide>
      <form onSubmit={onSubmit} className="grid gap-4 sm:grid-cols-2">
        {isNew && (
          <div className="flex gap-2 sm:col-span-2" role="radiogroup" aria-label="Type">
            {[['NEWS', 'News'], ['AD', 'Ad']].map(([v, l]) => (
              <button key={v} type="button" role="radio" aria-checked={type === v} onClick={() => setType(v)}
                className={`h-9 rounded-full border px-4 text-sm font-semibold ${type === v ? 'border-transparent bg-secondary-container text-on-secondary-container' : 'border-outline-variant text-on-surface-variant hover:bg-surface-variant'}`}>{l}</button>
            ))}
          </div>
        )}
        <Field label="Title" className="sm:col-span-2"><input name="title" required maxLength={200} defaultValue={item.title} className={inputCls} /></Field>
        {type === 'NEWS' && (
          <Field label="Body" className="sm:col-span-2">
            <textarea name="body" required maxLength={10000} rows={6} defaultValue={item.body ?? ''} className={`${inputCls} h-auto py-2`} />
          </Field>
        )}
        {isNew && cities ? (
          <Field label="Audience">
            <select name="city_id" defaultValue="" className={inputCls}>
              <option value="">All cities</option>
              {cities.map((c) => <option key={c.city_id} value={c.city_id}>{c.name}</option>)}
            </select>
          </Field>
        ) : <div className="hidden sm:block" />}
        {type === 'AD' && (
          <Field label="Format" hint="Full screen ads must be exactly 1080×1920 px.">
            <select name="creative_format" defaultValue={item.creative_format ?? 'BANNER'} className={inputCls}>
              <option value="BANNER">Banner</option>
              <option value="FULLSCREEN">Full screen</option>
            </select>
          </Field>
        )}
        <Field label="Starts"><input name="start_at" type="datetime-local" required defaultValue={toLocalInput(item.start_at)} className={inputCls} /></Field>
        <Field label="Ends"><input name="end_at" type="datetime-local" required defaultValue={toLocalInput(item.end_at ?? weekLater)} className={inputCls} /></Field>

        <div className="flex flex-col gap-2 sm:col-span-2">
          <span className="text-xs font-semibold tracking-[.5px] text-on-surface-variant">Image {type === 'AD' ? '(required)' : '(optional)'}</span>
          <div className="flex items-center gap-4">
            {media && <img src={media.media_url} alt="" className="h-20 max-w-40 rounded-lg border border-outline-variant object-contain" />}
            <div className="flex flex-col gap-1">
              <label className="inline-flex h-10 w-fit cursor-pointer items-center rounded-full border border-outline px-[18px] text-sm font-semibold text-primary hover:bg-primary-container/60">
                {uploading ? 'Uploading…' : media ? 'Replace image' : 'Upload image'}
                <input type="file" accept="image/png,image/jpeg" onChange={upload} className="sr-only" />
              </label>
              <span className="text-xs text-on-surface-variant">{media ? `${media.width}×${media.height} px` : 'JPEG or PNG, up to 5 MB'}</span>
            </div>
          </div>
          <ErrorText>{uploadError}</ErrorText>
        </div>

        <Field label="Publish as" className="sm:col-span-2">
          <select name="status" defaultValue={item.status === 'DRAFT' ? 'DRAFT' : 'SCHEDULED'} className={inputCls}>
            <option value="SCHEDULED">Scheduled: goes live at the start time</option>
            <option value="DRAFT">Draft: not shown to members</option>
          </select>
        </Field>
        <div className="sm:col-span-2"><ErrorText>{error}</ErrorText></div>
        <div className="flex items-center justify-between gap-2 sm:col-span-2">
          {!isNew ? <Button variant="text" className="text-error" onClick={cancelItem}>Cancel this item</Button> : <span />}
          <FormActions busy={busy} label={isNew ? 'Create' : 'Save'} onCancel={onClose} />
        </div>
      </form>
    </Modal>
  )
}
