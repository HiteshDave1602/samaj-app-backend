import { useState } from 'react'
import { api, fmtDateTime, qs, useFileUrl, useLoad, useToast } from '../../shared/api'
import { Badge, Button, Card, Detail, ErrorText, Field, Modal, PageHeader, Pager, StatusBadge, Table, Toolbar, inputCls } from '../../shared/ui'
import Decide from '../Decide'

const LIMIT = 50
const LOG_LIMIT = 20
const QUEUES = {
  moderate: { label: 'New profiles to moderate', params: { status: 'PENDING_MODERATION' } },
  photos: { label: 'Profiles with photos to check', params: { pending_photos: true } },
  APPROVED: { label: 'Approved', params: { status: 'APPROVED' } },
  REJECTED: { label: 'Rejected', params: { status: 'REJECTED' } },
  ARCHIVED: { label: 'Archived', params: { status: 'ARCHIVED' } },
  all: { label: 'All', params: {} },
}
const title = (s) => s && s[0] + s.slice(1).toLowerCase().replaceAll('_', ' ')

export default function Matrimony() {
  const [queue, setQueue] = useState('moderate')
  const [offset, setOffset] = useState(0)
  const [open, setOpen] = useState(null)
  const list = useLoad(`/cityadmin/matrimony/profiles${qs({ ...QUEUES[queue].params, limit: LIMIT, offset })}`)
  const [logOffset, setLogOffset] = useState(0)
  const log = useLoad(`/cityadmin/matrimony/decisions${qs({ limit: LOG_LIMIT, offset: logOffset })}`)

  return (
    <>
      <PageHeader title="Matrimony" subtitle="Profiles stay out of search until you approve them. Reject unsuitable photos first; approving a profile approves its remaining photos. Biodata is never shown here." />
      <Toolbar>
        <Field label="Show">
          <select value={queue} onChange={(e) => { setQueue(e.target.value); setOffset(0) }} className={inputCls}>
            {Object.entries(QUEUES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </Field>
      </Toolbar>
      <Table head={['Profile', 'Education & work', 'Managed by', 'Status', 'Updated', '']} error={list.error} loading={list.loading} empty="Nothing to review here.">
        {list.data?.items.map((p) => (
          <tr key={p.profile_id}>
            <td>
              <div className="font-semibold">{p.full_name ?? '—'}</div>
              <div className="text-xs text-on-surface-variant">{[title(p.gender), p.age && `${p.age} yrs`].filter(Boolean).join(' · ')}</div>
            </td>
            <td>
              <div>{title(p.education_level)}</div>
              {p.occupation && <div className="text-xs text-on-surface-variant">{p.occupation}</div>}
            </td>
            <td>{title(p.managed_by)}</td>
            <td>
              <div className="flex flex-col items-start gap-1">
                <StatusBadge status={p.status} />
                {p.pending_photo_count > 0 && <Badge tone="accent">{p.pending_photo_count} photo{p.pending_photo_count === 1 ? '' : 's'} to check</Badge>}
              </div>
            </td>
            <td className="whitespace-nowrap">{fmtDateTime(p.updated_at)}</td>
            <td className="text-right"><Button variant="text" className="h-8 px-3" onClick={() => setOpen(p.profile_id)}>Review</Button></td>
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
              {log.data.items.map((d, i) => {
                const approved = d.action.endsWith('APPROVE')
                const name = d.full_name ?? 'a deleted photo'
                return (
                  <li key={i} className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-4 py-3 text-sm">
                    <time className="w-40 shrink-0 text-xs text-on-surface-variant">{fmtDateTime(d.occurred_at)}</time>
                    <StatusBadge status={approved ? 'APPROVED' : 'REJECTED'} />
                    <div className="min-w-0 flex-1">
                      <span className="font-semibold">{d.admin_name ?? 'City admin'}</span>
                      {approved ? ' approved ' : ' rejected '}
                      {d.action.startsWith('PHOTO') && d.full_name && 'a photo of '}
                      {d.profile_id
                        ? <button type="button" onClick={() => setOpen(d.profile_id)} className="font-semibold text-primary hover:underline">{name}</button>
                        : <span className="font-semibold">{name}</span>}
                      {!d.action.startsWith('PHOTO') && <span className="text-on-surface-variant">'s profile</span>}
                      {d.reason && <div className="text-xs text-on-surface-variant">Reason: {d.reason}</div>}
                    </div>
                  </li>
                )
              })}
            </ol>
          )}
      </Card>
      {log.data && <Pager total={log.data.total} limit={LOG_LIMIT} offset={logOffset} onChange={setLogOffset} />}
      {open && <Review id={open} onClose={() => { setOpen(null); list.reload(); log.reload() }} />}
    </>
  )
}

function Review({ id, onClose }) {
  const load = useLoad(`/cityadmin/matrimony/profiles/${id}`)
  const [fresh, setFresh] = useState(null) // each decision returns the updated profile
  const toast = useToast()
  const p = fresh ?? load.data

  async function act(path, body, msg) {
    setFresh(await api(`/cityadmin/matrimony/${path}`, { method: 'POST', body }))
    toast(msg)
  }

  return (
    <Modal title="Matrimony profile" onClose={onClose} wide>
      {load.error ? <ErrorText>{load.error}</ErrorText> : !p ? <p className="text-on-surface-variant">Loading…</p> : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="font-display text-2xl font-semibold text-secondary">{p.full_name ?? '—'}</h3>
            <StatusBadge status={p.status} />
          </div>
          <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
            <Detail label="Gender / age">{[title(p.gender), p.age && `${p.age} yrs`].filter(Boolean).join(' · ') || '—'}</Detail>
            <Detail label="Managed by">{title(p.managed_by)}</Detail>
            <Detail label="Education">{title(p.education_level)}{p.education_detail && ` · ${p.education_detail}`}</Detail>
            <Detail label="Occupation">{p.occupation ?? '—'}</Detail>
            <Detail label="Family background" wide>{p.family_background}</Detail>
            <Detail label="About" wide>{p.about ?? '—'}</Detail>
            {p.moderation_reason && <Detail label="Rejection reason" wide>{p.moderation_reason}</Detail>}
          </dl>

          <div>
            <h4 className="mb-2 text-xs font-semibold tracking-[.5px] text-on-surface-variant uppercase">Photos</h4>
            {p.photos.length === 0 ? <p className="text-sm text-on-surface-variant">No photos.</p> : (
              <div className="grid gap-3 sm:grid-cols-2">
                {p.photos.map((ph) => (
                  <div key={ph.photo_id} className="flex flex-col gap-2 rounded-xl border border-outline-variant p-3">
                    <Photo path={ph.file_url} />
                    <div className="flex items-center justify-between gap-2">
                      <StatusBadge status={ph.status} />
                      <span className="text-xs text-on-surface-variant">{Math.round(ph.size_bytes / 1024)} KB</span>
                    </div>
                    {ph.rejection_reason && <p className="text-xs text-on-surface-variant">{ph.rejection_reason}</p>}
                    {ph.status === 'PENDING' && (
                      <Decide small
                        onApprove={() => act(`photos/${ph.photo_id}/approve`, undefined, 'Photo approved')}
                        onReject={(reason) => act(`photos/${ph.photo_id}/reject`, { reason }, 'Photo rejected')} />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {p.status === 'PENDING_MODERATION' && (
            <div className="border-t border-outline-variant pt-4">
              <Decide approveLabel="Approve profile"
                onApprove={() => act(`profiles/${id}/approve`, undefined, 'Profile approved. It now shows in search.')}
                onReject={(reason) => act(`profiles/${id}/reject`, { reason }, 'Profile rejected')} />
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}


function Photo({ path }) {
  const url = useFileUrl(path)
  if (url === null) return <div className="aspect-[3/4] animate-pulse rounded-lg bg-surface-variant" />
  if (!url) return <ErrorText>Photo couldn't be loaded.</ErrorText>
  return <img src={url} alt="Profile photo" className="aspect-[3/4] w-full rounded-lg bg-surface-variant object-contain" />
}
