import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './app/identity/pages/MynaIdentityApp.tsx'
import { startThemeFaviconSync } from './components/theme-favicon.ts'

startThemeFaviconSync()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
