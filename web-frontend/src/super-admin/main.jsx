import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../index.css'
import Panel from '../shared/Panel'
import Content from '../shared/Content'
import Overview from './pages/Overview'
import Cities from './pages/Cities'
import CityAdmins from './pages/CityAdmins'
import AuditLog from './pages/AuditLog'

const PAGES = [
  { id: 'overview', label: 'Overview', icon: 'M3 12l9-8 9 8M5 10v10h14V10', el: Overview },
  { id: 'cities', label: 'Cities', icon: 'M4 21V8l6-4v17M10 21V4l10 5v12M2 21h20M14 12h2M14 16h2', el: Cities },
  { id: 'admins', label: 'City Admins', icon: 'M16 19a4 4 0 0 0-8 0M12 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM19 8v6M22 11h-6', el: CityAdmins },
  { id: 'content', label: 'News & Ads', icon: 'M4 5h13v14H6a2 2 0 0 1-2-2V5ZM17 9h3v8a2 2 0 0 1-2 2M8 9h5M8 13h5', el: Content },
  { id: 'audit', label: 'Audit Log', icon: 'M9 5h10M9 12h10M9 19h10M5 5h.01M5 12h.01M5 19h.01', el: AuditLog },
]

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Panel role="SUPER_ADMIN" label="Super Admin" pages={PAGES} />
  </StrictMode>,
)
