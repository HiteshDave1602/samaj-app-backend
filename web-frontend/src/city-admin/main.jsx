import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../index.css'
import Panel from '../shared/Panel'
import Content from '../shared/Content'
import Dashboard from './pages/Dashboard'
import Members from './pages/Members'
import FamilyAdditions from './pages/FamilyAdditions'
import Matrimony from './pages/Matrimony'
import Panchang from './pages/Panchang'
import Import from './pages/Import'
import Export from './pages/Export'

const PAGES = [
  { id: 'dashboard', label: 'Dashboard', icon: 'M3 12l9-8 9 8M5 10v10h14V10', el: Dashboard },
  { id: 'members', label: 'Members', icon: 'M15 19a4 4 0 0 0-8 0M11 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM16 11l2 2 4-4', el: Members },
  { id: 'family', label: 'Family Additions', icon: 'M9 19a4 4 0 0 0-8 0M5 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM23 19a4 4 0 0 0-8 0M19 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM12 9v6M9 12h6', el: FamilyAdditions },
  { id: 'matrimony', label: 'Matrimony', icon: 'M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.5-7 10-7 10Z', el: Matrimony },
  { id: 'content', label: 'News & Ads', icon: 'M4 5h13v14H6a2 2 0 0 1-2-2V5ZM17 9h3v8a2 2 0 0 1-2 2M8 9h5M8 13h5', el: Content },
  { id: 'panchang', label: 'Panchang', icon: 'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4', el: Panchang },
  { id: 'import', label: 'Import', icon: 'M12 4v11M7 10l5 5 5-5M4 20h16', el: Import },
  { id: 'export', label: 'Export', icon: 'M12 15V4M7 9l5-5 5 5M4 20h16', el: Export },
]

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Panel role="CITY_ADMIN" label="City Admin" pages={PAGES} />
  </StrictMode>,
)
