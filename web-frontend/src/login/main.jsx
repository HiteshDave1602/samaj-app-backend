import { rootOptions } from '../shared/sentry'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../index.css'
import Login from '../shared/Login'

// Same theme as the panels (Panel saves the choice).
let saved = null
try { saved = localStorage.getItem('theme') } catch { /* private mode */ }
document.documentElement.dataset.theme = saved ?? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')

// One sign-in page for both panels; Login sends the person to the one their credentials are for.
createRoot(document.getElementById('root'), rootOptions).render(
  <StrictMode>
    <Login />
  </StrictMode>,
)
