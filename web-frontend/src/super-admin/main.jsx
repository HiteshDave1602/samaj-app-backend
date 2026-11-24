import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../index.css'
import Panel from '../shared/Panel'
import Content from '../shared/Content'
import Overview from './pages/Overview'
import Cities from './pages/Cities'
import CityAdmins from './pages/CityAdmins'
import AuditLog from './pages/AuditLog'
import Members from '../city-admin/pages/Members'
import Matrimony from '../city-admin/pages/Matrimony'
import Import from './pages/Import'
import Profile from '../city-admin/pages/Profile'
import Requests from '../shared/Requests'

const PAGES = [
  { id: 'overview', label: 'Overview', icon: 'M3 12l9-8 9 8M5 10v10h14V10', el: Overview },
  { id: 'notifications', label: 'Notifications', icon: 'M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.94 1.94 0 0 0 3.4 0', el: Requests },
  { id: 'cities', label: 'Cities', icon: 'M4 21V8l6-4v17M10 21V4l10 5v12M2 21h20M14 12h2M14 16h2', el: Cities },
  { id: 'admins', label: 'City Admins', icon: 'M16 19a4 4 0 0 0-8 0M12 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM19 8v6M22 11h-6', el: CityAdmins },
  { id: 'members', label: 'Members', icon: 'M15 19a4 4 0 0 0-8 0M11 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM16 11l2 2 4-4', el: Members },
  { id: 'matrimony', label: 'Matrimony', icon: 'M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.5-7 10-7 10Z', el: Matrimony },
  { id: 'import', label: 'Import', icon: 'M12 4v11M7 10l5 5 5-5M5 20h14', el: Import },
  { id: 'content', label: 'News & Ads', icon: 'M4 5h13v14H6a2 2 0 0 1-2-2V5ZM17 9h3v8a2 2 0 0 1-2 2M8 9h5M8 13h5', el: Content },
  { id: 'audit', label: 'Audit Log', icon: 'M9 5h10M9 12h10M9 19h10M5 5h.01M5 12h.01M5 19h.01', el: AuditLog },
  { id: 'profile', label: 'Profile', icon: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4 20a8 8 0 0 1 16 0', el: Profile },
]

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Panel role="SUPER_ADMIN" label="Super Admin" pages={PAGES} />
  </StrictMode>,
)
