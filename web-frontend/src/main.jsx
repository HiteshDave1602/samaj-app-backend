import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import SuperAdmin from './super-admin/SuperAdmin.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <SuperAdmin />
  </StrictMode>,
)
