import { fmtDateTime, useLoad } from '../../shared/api'
import { Badge, PageHeader, Stat, Table } from '../../shared/ui'

const hoursSince = (iso) => Math.floor((Date.now() - new Date(iso)) / 36e5)

/** Waiting time; 72 h is when the Super Admin sees it as overdue. */
export const Waiting = ({ since }) => {
  const h = hoursSince(since)
  return <Badge tone={h >= 72 ? 'error' : h >= 48 ? 'warning' : 'neutral'}>{h < 24 ? `${h} h` : `${Math.floor(h / 24)} days`}</Badge>
}

export default function Dashboard({ me }) {
  const panchang = useLoad('/cityadmin/panchang/status')
  const pending = useLoad('/cityadmin/members/pending?limit=10')
  const family = useLoad('/cityadmin/family-additions?status=PENDING&limit=1')
  const profiles = useLoad('/cityadmin/matrimony/profiles?status=PENDING_MODERATION&limit=1')
  const photos = useLoad('/cityadmin/matrimony/profiles?pending_photos=true&limit=1')
  const live = useLoad('/cityadmin/content?status=LIVE&limit=1')
  const p = panchang.data

  return (
    <>
      <PageHeader title={me.city_name} subtitle="What's waiting for you today. Registrations pending for more than 72 hours are escalated to the Super Admin." />

      {p?.error_code && (
        <div role="alert" className="mb-6 rounded-xl border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
          <b>Panchang missing for today.</b> {p.message} <a href="#panchang" className="font-semibold underline">Enter it now</a>
        </div>
      )}
      {p && !p.error_code && !p.tomorrow_available && (
        <div className="mb-6 rounded-xl border border-outline-variant bg-tertiary-container px-4 py-3 text-sm text-on-tertiary-container">
          Tomorrow's Panchang isn't in yet. <a href="#panchang" className="font-semibold underline">Check Panchang</a>
        </div>
      )}

      <div className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Pending registrations" value={pending.data?.total} href="#members" tone={pending.data?.total ? 'text-warning' : undefined} />
        <Stat label="Family additions" value={family.data?.total} href="#family" />
        <Stat label="Matrimony to review" value={profiles.data?.total} href="#matrimony"
          note={photos.data ? `${photos.data.total} profile${photos.data.total === 1 ? '' : 's'} with photos to check` : null} />
        <Stat label="Live news & ads" value={live.data?.total} href="#content" />
      </div>

      <h2 className="mb-1 text-xl leading-7 font-semibold">Oldest pending registrations</h2>
      <p className="mb-4 text-on-surface-variant">Verify each member's ID before approving. <a href="#members" className="font-semibold text-primary">Open the queue</a></p>
      <Table head={['Member', 'Family', 'Mobile', 'Registered', 'Waiting']} error={pending.error} loading={pending.loading} empty="No one is waiting. You're all caught up.">
        {pending.data?.items.map((m) => (
          <tr key={m.member_id}>
            <td className="font-semibold">{m.full_name ?? <span className="text-on-surface-variant italic">No name yet</span>}</td>
            <td>{m.family_name ?? '—'}</td>
            <td className="font-mono text-xs">{m.mobile_last4 ? `•••• ${m.mobile_last4}` : '—'}</td>
            <td className="whitespace-nowrap">{fmtDateTime(m.created_at)}</td>
            <td><Waiting since={m.created_at} /></td>
          </tr>
        ))}
      </Table>
    </>
  )
}
