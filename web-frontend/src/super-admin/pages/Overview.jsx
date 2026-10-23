import { fmtDateTime, useLoad } from '../../shared/api'
import { Badge, PageHeader, Stat, Table } from '../../shared/ui'

const hoursSince = (iso) => Math.floor((Date.now() - new Date(iso)) / 36e5)

export default function Overview() {
  const cities = useLoad('/superadmin/cities')
  const admins = useLoad('/superadmin/city-admins?status=ACTIVE')
  const live = useLoad('/superadmin/content?status=LIVE&limit=1')
  const overdue = useLoad('/superadmin/pending-members/overdue')

  const activeCities = cities.data?.filter((c) => c.is_active)
  const covered = new Set(admins.data?.map((a) => a.city_id))
  const uncovered = activeCities && admins.data ? activeCities.filter((c) => !covered.has(c.city_id)) : []

  return (
    <>
      <PageHeader title="Overview" subtitle="Cities, their admins, live content and registrations waiting too long for approval." />

      <div className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Active cities" value={activeCities?.length} href="#cities" />
        <Stat label="Active city admins" value={admins.data?.length} href="#admins" />
        <Stat label="Live news & ads" value={live.data?.total} href="#content" />
        <Stat label="Overdue registrations" value={overdue.data?.length} href="#overview" tone={overdue.data?.length ? 'text-warning' : undefined} />
      </div>

      {uncovered.length > 0 && (
        <div className="mb-8 rounded-xl border border-warning/30 bg-warning-container px-4 py-3 text-sm text-on-warning-container">
          <b>No active City Admin:</b> {uncovered.map((c) => c.name).join(', ')}. Registrations in these cities can't be approved. <a href="#admins" className="font-semibold underline">Add a City Admin</a>
        </div>
      )}

      <h2 className="mb-1 text-xl leading-7 font-semibold">Overdue registrations</h2>
      <p className="mb-4 text-on-surface-variant">First-time registrations pending for more than 72 hours, oldest first. Follow up with the city's admin.</p>
      <Table head={['Member', 'City', 'City Admin', 'Registered', 'Waiting']} error={overdue.error} loading={overdue.loading} empty="Nothing overdue. Every city is keeping up.">
        {overdue.data?.map((m) => (
          <tr key={m.member_id}>
            <td className="font-semibold">{m.full_name ?? <span className="text-on-surface-variant italic">No name yet</span>}</td>
            <td>{m.city_name}</td>
            <td>{m.city_admin_name ?? <Badge tone="error">None assigned</Badge>}</td>
            <td className="whitespace-nowrap">{fmtDateTime(m.created_at)}</td>
            <td><Badge tone="warning">{Math.floor(hoursSince(m.created_at) / 24)} days</Badge></td>
          </tr>
        ))}
      </Table>
    </>
  )
}
