import { useEffect, useState } from 'react'
import { fmtDateTime } from './api'
import { Badge, Card, ErrorText, PageHeader } from './ui'

// kind -> what the member sent, and the page where it's decided
const KINDS = {
  // detail: a city that isn't set up yet (Super Admin only): create it, then approve on the Members page
  REGISTRATION: {
    label: 'New registration',
    text: (d) => d ? `registered for ${d}, a city that isn't set up yet. Create it, then approve` : 'registered and is waiting for approval',
    page: 'members',
  },
  FAMILY: { label: 'Family addition', text: (d) => `asked to add ${d} to their family`, page: 'family' },
  PROFILE: { label: 'Matrimony profile', text: () => 'submitted a matrimony profile for review', page: 'matrimony' },
  PHOTOS: { label: 'Matrimony photos', text: (d) => `added ${d} photo${d === '1' ? '' : 's'} to review`, page: 'matrimony' },
  NEWS: { label: 'Member news', text: (d) => `submitted news: “${d}”`, page: 'content' },
}

/** The bell: every request members are waiting on, newest first. Opening it clears the badge. */
export default function Requests({ inbox, me }) {
  // What was unread when it first showed stays marked while the page is open, though /read has cleared it.
  const [fresh, setFresh] = useState(null)
  const items = inbox.data?.items
  if (items && !fresh) setFresh(new Set(items.filter((i) => i.unread).map((i) => `${i.kind}-${i.id}`)))
  useEffect(() => { if (inbox.unread) inbox.markSeen() }, [inbox.unread]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <PageHeader title="Notifications" subtitle="Requests members have sent that are waiting for a decision. Each one leaves this list once it's approved or rejected." />
      <ErrorText>{inbox.error}</ErrorText>
      {!items ? <p className="text-on-surface-variant">{inbox.error ? '' : 'Loading…'}</p>
        : !items.length ? <Card className="p-6 text-on-surface-variant">No requests waiting. You're all caught up.</Card>
        : (
          <Card className="divide-y divide-outline-variant">
            {items.map((i) => {
              const k = KINDS[i.kind]
              const isNew = i.unread || fresh?.has(`${i.kind}-${i.id}`)
              const href = inbox.hasPage(k.page) ? `#${k.page}` : null
              const Row = href ? 'a' : 'div'
              return (
                <Row key={`${i.kind}-${i.id}`} href={href ?? undefined}
                  className={`flex flex-wrap items-center gap-x-3 gap-y-1 px-5 py-4 ${href ? 'hover:bg-surface-variant/60' : ''} ${isNew ? 'bg-primary-container/30' : ''}`}>
                  {isNew && <span className="h-2 w-2 shrink-0 rounded-full bg-primary" aria-label="New" />}
                  <div className="min-w-0 flex-1">
                    <div className="text-sm"><b>{i.member_name ?? 'A member'}</b> {k.text(i.detail)}</div>
                    <div className="mt-0.5 text-xs text-on-surface-variant">
                      {fmtDateTime(i.at)}{me.role === 'SUPER_ADMIN' && i.city_name && ` · ${i.city_name}`}
                    </div>
                  </div>
                  <Badge tone="warning">{k.label}</Badge>
                </Row>
              )
            })}
          </Card>
        )}
      {inbox.data?.total > items?.length && (
        <p className="mt-3 text-sm text-on-surface-variant">Showing the newest {items.length} of {inbox.data.total}. Open each queue to see the rest.</p>
      )}
    </>
  )
}
